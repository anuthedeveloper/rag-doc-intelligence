from django.urls import path
from .views import DocumentUploadView, DocumentStatusView

urlpatterns = [
    path("upload", DocumentUploadView.as_view(), name="document-upload"),
    path("<int:pk>/status", DocumentStatusView.as_view(), name="document-status"),
]
