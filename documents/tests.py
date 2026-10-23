from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from documents.models import Document
from documents.tasks import _chunk_text, _extract_text


class DocumentTaskHelperTests(SimpleTestCase):
	def test_chunk_text_returns_overlapping_word_chunks(self):
		chunks = _chunk_text("one two three four five six seven", chunk_size=4, overlap=1)

		self.assertEqual(chunks, ["one two three four", "four five six seven"])

	def test_chunk_text_returns_no_chunks_for_empty_text(self):
		self.assertEqual(_chunk_text("  \n ", chunk_size=4, overlap=1), [])

	@patch("documents.tasks.PdfReader")
	def test_extract_text_joins_pages_and_ignores_empty_page_text(self, pdf_reader):
		pdf_reader.return_value.pages = [
			type("Page", (), {"extract_text": lambda self: "First page"})(),
			type("Page", (), {"extract_text": lambda self: None})(),
			type("Page", (), {"extract_text": lambda self: "Last page"})(),
		]

		self.assertEqual(_extract_text("sample.pdf"), "First page\n\nLast page")
		pdf_reader.assert_called_once_with("sample.pdf")


class DocumentEndpointTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.media_directory = TemporaryDirectory()
		self.addCleanup(self.media_directory.cleanup)
		self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
		self.settings_override.enable()
		self.addCleanup(self.settings_override.disable)

	def create_document(self, status=Document.STATUS_PENDING):
		return Document.objects.create(
			file=SimpleUploadedFile("contract.pdf", b"test pdf bytes", content_type="application/pdf"),
			original_filename="contract.pdf",
			status=status,
		)

	@patch("documents.views.process_document.delay")
	def test_upload_returns_accepted_document_and_enqueues_processing(self, enqueue):
		response = self.client.post(
			"/documents/upload",
			{"file": SimpleUploadedFile("contract.pdf", b"pdf bytes", content_type="application/pdf")},
			format="multipart",
		)

		self.assertEqual(response.status_code, 202)
		self.assertEqual(response.data["original_filename"], "contract.pdf")
		self.assertEqual(response.data["status"], Document.STATUS_PENDING)
		enqueue.assert_called_once_with(response.data["id"])
		self.assertTrue(Document.objects.filter(id=response.data["id"]).exists())

	@patch("documents.views.process_document.delay")
	def test_upload_requires_a_file(self, enqueue):
		response = self.client.post("/documents/upload", {}, format="multipart")

		self.assertEqual(response.status_code, 400)
		enqueue.assert_not_called()

	def test_status_returns_document_processing_details(self):
		document = self.create_document(status=Document.STATUS_FAILED)
		document.error_message = "PDF could not be read"
		document.save(update_fields=["error_message"])

		response = self.client.get(f"/documents/{document.id}/status")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["id"], document.id)
		self.assertEqual(response.data["status"], Document.STATUS_FAILED)
		self.assertEqual(response.data["error_message"], "PDF could not be read")
		self.assertIn("created_at", response.data)
		self.assertIn("updated_at", response.data)

	def test_status_returns_not_found_for_unknown_document(self):
		response = self.client.get("/documents/999/status")

		self.assertEqual(response.status_code, 404)


class DocumentProcessingTaskTests(TestCase):
	def setUp(self):
		self.media_directory = TemporaryDirectory()
		self.addCleanup(self.media_directory.cleanup)
		self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
		self.settings_override.enable()
		self.addCleanup(self.settings_override.disable)
		self.document = Document.objects.create(
			file=SimpleUploadedFile("contract.pdf", b"pdf bytes"),
			original_filename="contract.pdf",
		)

	@patch("retrieval.models.Chunk.objects.bulk_create")
	@patch("retrieval.embeddings.embed_texts", return_value=[[0.1, 0.2]])
	@patch("documents.tasks._extract_text", return_value="important contract terms")
	def test_processing_stores_chunks_and_marks_document_ready(
		self, extract_text, embed_texts, bulk_create
	):
		from documents.tasks import process_document

		process_document.run(self.document.id)

		self.document.refresh_from_db()
		self.assertEqual(self.document.status, Document.STATUS_READY)
		self.assertEqual(self.document.error_message, "")
		embed_texts.assert_called_once_with(["important contract terms"])
		self.assertEqual(bulk_create.call_count, 1)
		created_chunks = bulk_create.call_args.args[0]
		self.assertEqual(len(created_chunks), 1)
		self.assertEqual(created_chunks[0].text, "important contract terms")
		self.assertEqual(created_chunks[0].chunk_index, 0)

	@patch("retrieval.embeddings.embed_texts", side_effect=RuntimeError("provider unavailable"))
	@patch("documents.tasks._extract_text", return_value="important contract terms")
	def test_processing_records_failure_and_retries(self, extract_text, embed_texts):
		from documents.tasks import process_document

		with self.assertRaisesMessage(RuntimeError, "provider unavailable"):
			process_document.run(self.document.id)

		self.document.refresh_from_db()
		self.assertEqual(self.document.status, Document.STATUS_FAILED)
		self.assertEqual(self.document.error_message, "provider unavailable")
