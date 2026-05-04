from __future__ import annotations

from time import perf_counter

from .config import DEFAULT_EMBED_MODEL, DEFAULT_LLM_MODEL, DEFAULT_TOP_K
from .generation import build_context, generate_answer
from .ingestion import get_ingested_summary, ingest_entities, initialize_storage
from .retrieval import clear_retrieval_caches, is_supported_query, retrieve_context
from .storage import collection_count


class WikiRAGService:
    def __init__(
        self,
        llm_model: str = DEFAULT_LLM_MODEL,
        embedding_model: str = DEFAULT_EMBED_MODEL,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        self.llm_model = llm_model
        self.embedding_model = embedding_model
        self.top_k = top_k
        self._answer_cache: dict[str, dict[str, object]] = {}
        initialize_storage(reset=False)

    def ingest(self, reset: bool = False) -> list[dict[str, object]]:
        results = ingest_entities(reset=reset, embedding_model=self.embedding_model)
        clear_retrieval_caches()
        self._answer_cache.clear()
        return results

    def ask(self, query: str) -> dict[str, object]:
        cache_key = query.strip().lower()
        cached_result = self._answer_cache.get(cache_key)
        if cached_result is not None:
            return {
                **cached_result,
                "timings": {"retrieve_ms": 0.0, "generate_ms": 0.0, "total_ms": 0.0},
                "cached": True,
            }
        if collection_count() == 0:
            return {
                "answer": "I don't know. The local index is empty, so please ingest the Wikipedia data first.",
                "query_types": [],
                "context": [],
                "timings": {"retrieve_ms": 0.0, "generate_ms": 0.0, "total_ms": 0.0},
                "cached": False,
            }
        if not is_supported_query(query):
            return {
                "answer": "I don't know. This question is outside the supported local Wikipedia dataset for famous people and places.",
                "query_types": [],
                "context": [],
                "timings": {"retrieve_ms": 0.0, "generate_ms": 0.0, "total_ms": 0.0},
                "cached": False,
            }
        total_start = perf_counter()
        retrieve_start = perf_counter()
        query_types, chunks = retrieve_context(
            query=query,
            embedding_model=self.embedding_model,
            top_k=self.top_k,
        )
        retrieve_ms = (perf_counter() - retrieve_start) * 1000.0
        generate_start = perf_counter()
        answer = generate_answer(query=query, chunks=chunks, llm_model=self.llm_model)
        generate_ms = (perf_counter() - generate_start) * 1000.0
        total_ms = (perf_counter() - total_start) * 1000.0
        result = {
            "answer": answer,
            "query_types": sorted(query_types),
            "context": [
                {
                    "chunk_id": chunk.chunk_id,
                    "entity_name": chunk.entity_name,
                    "entity_type": chunk.entity_type,
                    "source_url": chunk.source_url,
                    "distance": chunk.distance,
                    "text": chunk.text,
                }
                for chunk in chunks
            ],
            "timings": {
                "retrieve_ms": round(retrieve_ms, 1),
                "generate_ms": round(generate_ms, 1),
                "total_ms": round(total_ms, 1),
            },
            "cached": False,
        }
        self._answer_cache[cache_key] = {
            "answer": result["answer"],
            "query_types": result["query_types"],
            "context": result["context"],
        }
        return result

    def stats(self) -> dict[str, object]:
        return {
            "indexed_chunks": collection_count(),
            "documents": get_ingested_summary(),
        }

    def preview_context(self, query: str) -> str:
        _, chunks = retrieve_context(
            query=query,
            embedding_model=self.embedding_model,
            top_k=self.top_k,
        )
        return build_context(query, chunks)
