import os
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from pgvector.django import L2Distance

from retrieval import embeddings
from retrieval.search import retrieve_relevant_chunks


class EmbeddingClientTests(SimpleTestCase):
	@patch.dict(os.environ, {"EMBEDDING_PROVIDER_API_KEY": "test-key"})
	@patch("retrieval.embeddings.requests.post")
	def test_embed_texts_sends_request_and_orders_vectors_by_index(self, post):
		response = Mock()
		response.json.return_value = {
			"data": [
				{"index": 1, "embedding": [0.2, 0.3]},
				{"index": 0, "embedding": [0.1, 0.2]},
			]
		}
		post.return_value = response

		result = embeddings.embed_texts(["first", "second"])

		self.assertEqual(result, [[0.1, 0.2], [0.2, 0.3]])
		post.assert_called_once_with(
			embeddings.EMBEDDINGS_URL,
			headers={"Authorization": "Bearer test-key"},
			json={"model": "text-embedding-3-small", "input": ["first", "second"]},
			timeout=30,
		)
		response.raise_for_status.assert_called_once_with()

	@patch.dict(os.environ, {}, clear=True)
	def test_embed_texts_requires_provider_api_key(self):
		with self.assertRaisesMessage(RuntimeError, "EMBEDDING_PROVIDER_API_KEY is not set"):
			embeddings.embed_texts(["text"])

	@patch("retrieval.embeddings.embed_texts", return_value=[[0.7, 0.8]])
	def test_embed_query_returns_single_embedding(self, embed_texts):
		result = embeddings.embed_query("search phrase")

		self.assertEqual(result, [0.7, 0.8])
		embed_texts.assert_called_once_with(["search phrase"])


class RetrievalSearchTests(SimpleTestCase):
	@patch("retrieval.search.embed_query", return_value=[0.1, 0.2])
	@patch("retrieval.search.Chunk.objects.filter")
	def test_search_scopes_to_document_and_limits_results(self, filter_chunks, embed_query):
		expected = [Mock(), Mock()]
		ordered = Mock()
		ordered.__getitem__ = Mock(return_value=expected)
		filter_chunks.return_value.order_by.return_value = ordered

		result = retrieve_relevant_chunks(document_id=17, question="find this", top_k=2)

		self.assertEqual(result, expected)
		embed_query.assert_called_once_with("find this")
		filter_chunks.assert_called_once_with(document_id=17)
		ordering = filter_chunks.return_value.order_by.call_args.args[0]
		self.assertIsInstance(ordering, L2Distance)
		self.assertEqual(ordered.__getitem__.call_args.args[0], slice(None, 2, None))

	@patch("retrieval.search.embed_query", return_value=[0.1, 0.2])
	@patch("retrieval.search.Chunk.objects.filter")
	def test_search_uses_configured_top_k_when_not_provided(self, filter_chunks, embed_query):
		from django.conf import settings

		ordered = Mock()
		ordered.__getitem__ = Mock(return_value=[])
		filter_chunks.return_value.order_by.return_value = ordered

		retrieve_relevant_chunks(document_id=5, question="query")

		self.assertEqual(ordered.__getitem__.call_args.args[0].stop, settings.TOP_K_CHUNKS)
