# from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.response import Response

from .models import Document
from .serializers import DocumentUploadSerializer, DocumentStatusSerializer
from .tasks import process_document

# Create your views here.

class DocumentUploadView(generics.CreateAPIView):
    """
    POST /documents/upload

    Accepts a multipart file upload, saves the Document record,
    and kicks off async extraction + chunking + embedding.
    """

    queryset = Document.objects.all()
    serializer_class = DocumentUploadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save()

        # Fire off the async pipeline; the request returns immediately.
        process_document.delay(document.id)

        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class DocumentStatusView(generics.RetrieveAPIView):
    """GET /documents/{id}/status"""

    queryset = Document.objects.all()
    serializer_class = DocumentStatusSerializer
