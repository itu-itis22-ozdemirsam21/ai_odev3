from __future__ import annotations

from dataclasses import dataclass
import json
from urllib import error, request

from .config import OLLAMA_BASE_URL, REQUEST_TIMEOUT_SECONDS


class OllamaError(RuntimeError):
    """Raised when the local Ollama service cannot complete a request."""


@dataclass
class OllamaClient:
    base_url: str = OLLAMA_BASE_URL
    timeout_seconds: int = REQUEST_TIMEOUT_SECONDS

    def _post(self, path: str, payload: dict) -> dict:
        raw_payload = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            url=f"{self.base_url}{path}",
            data=raw_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise OllamaError(
                f"Ollama request failed with status {exc.code}: {body}"
            ) from exc
        except error.URLError as exc:
            raise OllamaError(
                "Failed to contact Ollama. Make sure the local Ollama server is running."
            ) from exc

    def generate(self, model: str, prompt: str) -> str:
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2},
            }
            body = self._post("/api/generate", payload)
        except OllamaError:
            raise
        except Exception as exc:
            raise OllamaError(
                "Failed to generate a response from Ollama. "
                "Make sure the Ollama server is running locally."
            ) from exc

        return body.get("response", "").strip()

    def embed_many(self, model: str, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            body = self._post("/api/embed", {"model": model, "input": texts})
            embeddings = body.get("embeddings")
            if embeddings:
                return embeddings
        except OllamaError as exc:
            if "status 404" not in str(exc):
                raise OllamaError(
                    "Failed to fetch embeddings from Ollama."
                ) from exc
        except Exception as exc:
            raise OllamaError(
                "Failed to fetch embeddings from Ollama. "
                "Make sure the Ollama server is running locally."
            ) from exc

        vectors: list[list[float]] = []
        for text in texts:
            try:
                body = self._post("/api/embeddings", {"model": model, "prompt": text})
            except Exception as exc:
                raise OllamaError("Failed to fetch embeddings from Ollama.") from exc
            embedding = body.get("embedding")
            if not embedding:
                raise OllamaError("Ollama returned an empty embedding vector.")
            vectors.append(embedding)
        return vectors
