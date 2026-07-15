from rest_framework import serializers
from .models import Document


class DocumentUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "file", "original_filename", "status"]
        read_only_fields = ["id", "status"]

    def create(self, validated_data):
        uploaded_file = validated_data["file"]
        validated_data.setdefault("original_filename", uploaded_file.name)
        return super().create(validated_data)


class DocumentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "original_filename", "status", "error_message", "created_at", "updated_at"]
