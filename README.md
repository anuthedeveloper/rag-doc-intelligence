# Document intelligence / RAG pipeline

A backend service that ingests PDFs, chunks and embeds them into Postgres
(via pgvector), and answers questions about them using retrieval-augmented
generation with Claude.

## Stack
- Django REST Framework
- PostgreSQL + pgvector
- Celery + Redis for async ingestion
- Anthropic API for answer generation

## Local setup

1. Copy the environment template and fill in your keys:
   ```bash
   cp .env.example .env
   ```
   You'll need an `ANTHROPIC_API_KEY` and an `EMBEDDING_PROVIDER_API_KEY`
   (any OpenAI-compatible embeddings endpoint).

2. Build and start everything:
   ```bash
   docker-compose up --build
   ```

3. Run migrations (in a separate terminal):
   ```bash
   docker-compose exec web python manage.py migrate
   ```

## API

**Upload a document**
```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@/path/to/your.pdf"
```
Returns a `document_id` and kicks off async processing.

**Check processing status**
```bash
curl http://localhost:8000/documents/1/status
```

**Ask a question**
```bash
curl -X POST http://localhost:8000/qa/ask \
  -H "Content-Type: application/json" \
  -d '{"document_id": 1, "question": "What does section 3 say about liability?"}'
```

## Project layout
- `documents/` — upload endpoint, PDF text extraction, chunking (Celery task)
- `retrieval/` — Chunk model (pgvector), embedding client, similarity search
- `qa/` — RAG question-answering endpoint
- `.github/workflows/deploy.yml` — CI/CD to Azure Container Registry + App Service

## Next steps / ideas to extend this for a portfolio
- Swap word-based chunking for token-aware chunking (tiktoken) for more precise chunk sizes
- Add auth (DRF token or JWT) so documents are scoped per user
- Add a `/documents/{id}/chunks` debug endpoint to inspect what got embedded
- Stream the LLM answer back with server-sent events instead of a single blocking response
- Add pytest coverage for the chunking logic and retrieval ranking
