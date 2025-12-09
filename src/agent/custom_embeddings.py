"""Custom Ollama embeddings using direct HTTP requests to avoid Python client issues."""
import requests
from typing import List
from langchain_core.embeddings import Embeddings
from ..utils.logging import get_logger

logger = get_logger("custom_embeddings")


class DirectOllamaEmbeddings(Embeddings):
    """
    Custom Ollama embeddings that use direct HTTP requests.

    This avoids issues with the ollama Python client creating proxy ports.
    """

    def __init__(self, model: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        """
        Initialize direct Ollama embeddings.

        Args:
            model: The Ollama model to use for embeddings
            base_url: The base URL of the Ollama server
        """
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.embed_url = f"{self.base_url}/api/embed"
        logger.debug(f"Initialized DirectOllamaEmbeddings with model={model}, url={self.embed_url}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of documents.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings (each embedding is a list of floats)
        """
        embeddings = []

        for text in texts:
            embedding = self._embed_single(text)
            embeddings.append(embedding)

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query.

        Args:
            text: The text to embed

        Returns:
            The embedding as a list of floats
        """
        return self._embed_single(text)

    def _embed_single(self, text: str) -> List[float]:
        """
        Embed a single piece of text using direct HTTP request.

        Args:
            text: The text to embed

        Returns:
            The embedding as a list of floats
        """
        try:
            response = requests.post(
                self.embed_url,
                json={
                    "model": self.model,
                    "input": text
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # The response contains an "embeddings" array with one embedding
            if "embeddings" in data and len(data["embeddings"]) > 0:
                return data["embeddings"][0]
            else:
                raise ValueError(f"Unexpected response format: {data}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get embedding: {e}")
            raise RuntimeError(f"Ollama embedding request failed: {e}") from e
