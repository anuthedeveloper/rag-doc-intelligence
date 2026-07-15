from django.db import models
from django.conf import settings
from pgvector.django import VectorField

from documents.models import Document
# Create your models here.


class Chunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()
    embedding = VectorField(dimensions=settings.EMBEDDING_DIMENSIONS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id", "chunk_index"]

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document_id}"
