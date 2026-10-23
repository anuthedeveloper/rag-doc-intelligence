from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from documents.models import Document
from qa.prompts import build_user_prompt


class AskEndpointTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.media_directory = TemporaryDirectory()
		self.addCleanup(self.media_directory.cleanup)
		self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
		self.settings_override.enable()
		self.addCleanup(self.settings_override.disable)
		self.document = Document.objects.create(
			file=SimpleUploadedFile("guide.pdf", b"pdf bytes"),
			original_filename="guide.pdf",
		)

	def ask(self, data):
		return self.client.post("/qa/ask", data, format="json")

	def test_ask_requires_document_id_and_question(self):
		for payload in ({}, {"document_id": self.document.id}, {"question": "What is covered?"}):
			with self.subTest(payload=payload):
				response = self.ask(payload)
				self.assertEqual(response.status_code, 400)
				self.assertEqual(response.data["error"], "document_id and question are required")

	def test_ask_returns_not_found_for_unknown_document(self):
		response = self.ask({"document_id": 999, "question": "What is covered?"})

		self.assertEqual(response.status_code, 404)
		self.assertEqual(response.data["error"], "document not found")

	def test_ask_rejects_document_that_is_not_ready(self):
		response = self.ask({"document_id": self.document.id, "question": "What is covered?"})

		self.assertEqual(response.status_code, 409)
		self.assertIn("document is not ready yet", response.data["error"])

	@patch("qa.views.retrieve_relevant_chunks", return_value=[])
	def test_ask_returns_not_found_when_retrieval_has_no_chunks(self, retrieve):
		self.document.status = Document.STATUS_READY
		self.document.save(update_fields=["status"])

		response = self.ask({"document_id": self.document.id, "question": "What is covered?"})

		self.assertEqual(response.status_code, 404)
		self.assertEqual(response.data["error"], "no relevant content found")
		retrieve.assert_called_once_with(self.document.id, "What is covered?")

	@patch("qa.views.anthropic.Anthropic")
	@patch("qa.views.retrieve_relevant_chunks")
	def test_ask_returns_generated_answer_and_source_excerpts(self, retrieve, anthropic_client):
		self.document.status = Document.STATUS_READY
		self.document.save(update_fields=["status"])
		chunk = SimpleNamespace(chunk_index=4, text="The warranty lasts two years.")
		retrieve.return_value = [chunk]
		client = anthropic_client.return_value
		client.messages.create.return_value.content = [
			SimpleNamespace(type="text", text="The warranty lasts two years."),
			SimpleNamespace(type="tool_use", text="ignored"),
		]

		response = self.ask({"document_id": self.document.id, "question": "How long is the warranty?"})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data, {
			"answer": "The warranty lasts two years.",
			"sources": [{"chunk_index": 4, "text": "The warranty lasts two years."}],
		})
		prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
		self.assertIn("How long is the warranty?", prompt)
		self.assertIn("The warranty lasts two years.", prompt)

	def test_user_prompt_numbers_each_excerpt(self):
		chunks = [SimpleNamespace(text="First excerpt"), SimpleNamespace(text="Second excerpt")]

		prompt = build_user_prompt("Summarize this", chunks)

		self.assertIn("[Excerpt 1]\nFirst excerpt", prompt)
		self.assertIn("[Excerpt 2]\nSecond excerpt", prompt)
		self.assertTrue(prompt.endswith("Question: Summarize this"))
