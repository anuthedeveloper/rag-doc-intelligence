from django.conf import settings
from pgvector.django import L2Distance

from .embeddings import embed_query
from .models import Chunk


def retrieve_relevant_chunks(document_id, question, top_k=None):
    """
    Embed the question, then return the top_k most similar chunks for the
    given document, ordered by distance (closest first).
    """
    top_k = top_k or settings.TOP_K_CHUNKS
    query_embedding = embed_query(question)

    return list(
        Chunk.objects.filter(document_id=document_id)
        .order_by(L2Distance("embedding", query_embedding))[:top_k]
    )
