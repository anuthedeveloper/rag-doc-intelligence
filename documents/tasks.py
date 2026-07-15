from celery import shared_task
from django.conf import settings
from pypdf import PdfReader

from .models import Document


def _extract_text(file_path):
    reader = PdfReader(file_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _chunk_text(text, chunk_size=None, overlap=None):
    """
    Simple word-based chunking with overlap. Good enough for a first pass;
    swap for a token-aware splitter (e.g. tiktoken) if precision matters later.
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE_TOKENS
    overlap = overlap or settings.CHUNK_OVERLAP_TOKENS

    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start = end - overlap
    return [c for c in chunks if c.strip()]


@shared_task(bind=True, max_retries=3)
def process_document(self, document_id):
    from retrieval.embeddings import embed_texts
    from retrieval.models import Chunk

    document = Document.objects.get(id=document_id)
    document.status = Document.STATUS_PROCESSING
    document.save(update_fields=["status"])

    try:
        text = _extract_text(document.file.path)
        chunks = _chunk_text(text)

        if not chunks:
            raise ValueError("No extractable text found in document")

        embeddings = embed_texts(chunks)

        Chunk.objects.bulk_create(
            [
                Chunk(document=document, text=chunk, embedding=embedding, chunk_index=i)
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
            ]
        )

        document.status = Document.STATUS_READY
        document.save(update_fields=["status"])

    except Exception as exc:
        document.status = Document.STATUS_FAILED
        document.error_message = str(exc)
        document.save(update_fields=["status", "error_message"])
        raise self.retry(exc=exc, countdown=10)
