# from django.shortcuts import render

import anthropic
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from documents.models import Document
from retrieval.search import retrieve_relevant_chunks
from .prompts import RAG_SYSTEM_PROMPT, build_user_prompt

# Create your views here.

class AskView(APIView):
    """
    POST /qa/ask
    Body: {"document_id": 1, "question": "What does section 3 say about liability?"}
    """

    def post(self, request):
        document_id = request.data.get("document_id")
        question = request.data.get("question")

        if not document_id or not question:
            return Response(
                {"error": "document_id and question are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return Response({"error": "document not found"}, status=status.HTTP_404_NOT_FOUND)

        if document.status != Document.STATUS_READY:
            return Response(
                {"error": f"document is not ready yet (status: {document.status})"},
                status=status.HTTP_409_CONFLICT,
            )

        chunks = retrieve_relevant_chunks(document_id, question)
        if not chunks:
            return Response({"error": "no relevant content found"}, status=status.HTTP_404_NOT_FOUND)

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1000,
            system=RAG_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(question, chunks)}],
        )

        answer_text = "".join(
            block.text for block in message.content if block.type == "text"
        )

        return Response(
            {
                "answer": answer_text,
                "sources": [
                    {"chunk_index": c.chunk_index, "text": c.text[:200]} for c in chunks
                ],
            }
        )
