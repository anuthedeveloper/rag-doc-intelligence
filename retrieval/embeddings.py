"""
Thin wrapper around an embedding provider. Claude's API does not currently
expose an embeddings endpoint, so this uses an OpenAI-compatible embeddings
API (works with OpenAI directly, or any provider that mirrors that schema,
e.g. Azure OpenAI). Swap the implementation here if you standardize on a
different provider later -- nothing else in the codebase needs to change.
"""

import os
import requests
from django.conf import settings

EMBEDDINGS_URL = os.environ.get(
    "EMBEDDINGS_API_URL", "https://api.openai.com/v1/embeddings"
)


def embed_texts(texts):
    """
    Given a list of strings, return a list of embedding vectors (list[float]),
    one per input string, in the same order.
    """
    api_key = os.environ.get("EMBEDDING_PROVIDER_API_KEY")
    if not api_key:
        raise RuntimeError("EMBEDDING_PROVIDER_API_KEY is not set")

    response = requests.post(
        EMBEDDINGS_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": settings.EMBEDDING_MODEL, "input": texts},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()["data"]

    # The API guarantees results are returned in input order via the
    # "index" field, but we sort defensively rather than assume it.
    data.sort(key=lambda item: item["index"])
    return [item["embedding"] for item in data]


def embed_query(text):
    return embed_texts([text])[0]
