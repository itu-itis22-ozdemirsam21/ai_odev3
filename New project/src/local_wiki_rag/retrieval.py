from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Optional

from .config import DEFAULT_EMBED_MODEL, DEFAULT_TOP_K
from .entities import PEOPLE, PLACES
from .ollama_client import OllamaClient
from .storage import fetch_embeddings


PERSON_KEYWORDS = {
    "who",
    "person",
    "famous",
    "known",
    "discover",
    "invent",
    "scientist",
    "artist",
    "writer",
    "singer",
    "player",
    "born",
    "died",
}

PLACE_KEYWORDS = {
    "where",
    "place",
    "located",
    "country",
    "city",
    "landmark",
    "monument",
    "mountain",
    "tower",
    "wall",
    "temple",
    "palace",
    "canyon",
    "river",
}

MIXED_HINTS = {"compare", "difference", "similar", "both"}
UNSUPPORTED_ROLE_KEYWORDS = {"president", "prime", "minister", "ceo", "mayor", "governor"}
UNSUPPORTED_TOPIC_KEYWORDS = {"food", "health", "healthy", "nutrition", "recipe", "diet"}
UNSUPPORTED_SPORT_QUERY_KEYWORDS = {"season", "record", "winner", "won"}
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}
GENERIC_QUERY_TOKENS = PERSON_KEYWORDS | PLACE_KEYWORDS | {"famous", "known", "about"}


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    entity_name: str
    entity_type: str
    source_url: str
    distance: float


@dataclass
class CachedEmbeddingRow:
    chunk_id: str
    text: str
    entity_name: str
    entity_type: str
    source_url: str
    chunk_index: int
    embedding: list[float]
    entity_tokens: set[str]
    chunk_tokens: set[str]
    normalized_entity_name: str


_EMBEDDING_CACHE: dict[str, list[CachedEmbeddingRow]] = {}
_QUERY_EMBED_CACHE: dict[tuple[str, str], list[float]] = {}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _tokenize(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z]+", value.lower())
        if len(token) > 2 and token not in STOPWORDS
    }


PERSON_NAMES = {_normalize(name): name for name in PEOPLE}
PLACE_NAMES = {_normalize(name): name for name in PLACES}


def clear_retrieval_caches() -> None:
    _EMBEDDING_CACHE.clear()
    _QUERY_EMBED_CACHE.clear()


def _cache_key(entity_type: Optional[str]) -> str:
    return entity_type or "__all__"


def _load_cached_embeddings(entity_type: Optional[str]) -> list[CachedEmbeddingRow]:
    key = _cache_key(entity_type)
    cached_rows = _EMBEDDING_CACHE.get(key)
    if cached_rows is not None:
        return cached_rows

    parsed_rows: list[CachedEmbeddingRow] = []
    for row in fetch_embeddings(entity_type):
        entity_name = row["entity_name"]
        chunk_text = row["chunk_text"]
        parsed_rows.append(
            CachedEmbeddingRow(
                chunk_id=row["id"],
                text=chunk_text,
                entity_name=entity_name,
                entity_type=row["entity_type"],
                source_url=row["source_url"],
                chunk_index=row["chunk_index"],
                embedding=json.loads(row["embedding_json"]),
                entity_tokens=_tokenize(entity_name),
                chunk_tokens=_tokenize(chunk_text),
                normalized_entity_name=_normalize(entity_name),
            )
        )

    _EMBEDDING_CACHE[key] = parsed_rows
    return parsed_rows


def detect_query_types(query: str) -> set[str]:
    normalized = _normalize(query)
    detected: set[str] = set()
    matched_person = False
    matched_place = False

    for name in PERSON_NAMES:
        if name in normalized:
            detected.add("person")
            matched_person = True
            break
    for name in PLACE_NAMES:
        if name in normalized:
            detected.add("place")
            matched_place = True
            break

    tokens = set(re.findall(r"[a-zA-Z]+", normalized))
    person_score = len(tokens & PERSON_KEYWORDS)
    place_score = len(tokens & PLACE_KEYWORDS)

    if matched_person and matched_place:
        return {"person", "place"}

    if tokens & MIXED_HINTS and person_score and place_score:
        return {"person", "place"}

    if detected:
        return detected

    if person_score > place_score:
        return {"person"}
    if place_score > person_score:
        return {"place"}
    return {"person", "place"}


def detect_mentioned_entities(query: str, allowed_types: Optional[set[str]] = None) -> list[tuple[str, str]]:
    normalized = _normalize(query)
    matches: list[tuple[str, str]] = []

    if allowed_types is None or "person" in allowed_types:
        for normalized_name, original_name in PERSON_NAMES.items():
            if normalized_name in normalized:
                matches.append((original_name, "person"))

    if allowed_types is None or "place" in allowed_types:
        for normalized_name, original_name in PLACE_NAMES.items():
            if normalized_name in normalized:
                matches.append((original_name, "place"))

    return matches


def is_supported_query(query: str) -> bool:
    mentioned_entities = detect_mentioned_entities(query)
    if mentioned_entities:
        return True

    tokens = set(re.findall(r"[a-zA-Z]+", query.lower()))

    if tokens & UNSUPPORTED_ROLE_KEYWORDS:
        return False
    if tokens & UNSUPPORTED_TOPIC_KEYWORDS:
        return False
    if len(tokens & UNSUPPORTED_SPORT_QUERY_KEYWORDS) >= 2:
        return False

    detected_types = detect_query_types(query)
    if "person" in detected_types and tokens & PERSON_KEYWORDS:
        return True
    if "place" in detected_types and tokens & PLACE_KEYWORDS:
        return True
    if tokens & MIXED_HINTS:
        return True

    return False


def _score_row(
    query: str,
    query_embedding: list[float],
    row: CachedEmbeddingRow,
    entity_name_filter: Optional[str],
) -> float:
    normalized_query = _normalize(query)
    query_tokens = _tokenize(query)
    salient_tokens = query_tokens - GENERIC_QUERY_TOKENS

    cosine = _cosine_similarity(query_embedding, row.embedding)
    score = cosine

    if row.normalized_entity_name in normalized_query:
        score += 0.8

    if entity_name_filter and row.entity_name == entity_name_filter:
        score += 0.35

    entity_overlap = len(query_tokens & row.entity_tokens)
    chunk_overlap = len(query_tokens & row.chunk_tokens)
    salient_overlap = len(salient_tokens & row.chunk_tokens)

    score += min(0.35, entity_overlap * 0.18)
    score += min(0.25, chunk_overlap * 0.06)
    score += min(0.45, salient_overlap * 0.22)

    if row.chunk_index == 0:
        score += 0.08

    return score


def _query_collection(
    query: str,
    query_embedding: list[float],
    entity_type: Optional[str],
    top_k: int,
    entity_name_filter: Optional[str] = None,
    diversify_by_entity: bool = True,
) -> list[RetrievedChunk]:
    scored_chunks: list[tuple[float, RetrievedChunk]] = []
    for row in _load_cached_embeddings(entity_type):
        if entity_name_filter and row.entity_name != entity_name_filter:
            continue

        score = _score_row(query, query_embedding, row, entity_name_filter)
        distance = 1.0 - _cosine_similarity(query_embedding, row.embedding)
        scored_chunks.append(
            (
                score,
                RetrievedChunk(
                    chunk_id=row.chunk_id,
                    text=row.text,
                    entity_name=row.entity_name,
                    entity_type=row.entity_type,
                    source_url=row.source_url,
                    distance=float(distance),
                ),
            )
        )

    scored_chunks.sort(key=lambda item: (-item[0], item[1].distance))

    if not diversify_by_entity:
        return [chunk for _, chunk in scored_chunks[:top_k]]

    selected: list[RetrievedChunk] = []
    seen_entities: set[str] = set()
    used_chunk_ids: set[str] = set()

    for _, chunk in scored_chunks:
        if chunk.entity_name in seen_entities:
            continue
        selected.append(chunk)
        seen_entities.add(chunk.entity_name)
        used_chunk_ids.add(chunk.chunk_id)
        if len(selected) == top_k:
            return selected

    for _, chunk in scored_chunks:
        if chunk.chunk_id in used_chunk_ids:
            continue
        selected.append(chunk)
        used_chunk_ids.add(chunk.chunk_id)
        if len(selected) == top_k:
            break

    return selected


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def retrieve_context(
    query: str,
    embedding_model: str = DEFAULT_EMBED_MODEL,
    top_k: int = DEFAULT_TOP_K,
) -> tuple[set[str], list[RetrievedChunk]]:
    types = detect_query_types(query)
    mentioned_entities = detect_mentioned_entities(query, allowed_types=types)
    embed_cache_key = (embedding_model, query.strip().lower())
    query_embedding = _QUERY_EMBED_CACHE.get(embed_cache_key)
    if query_embedding is None:
        ollama = OllamaClient()
        query_embedding = ollama.embed_many(embedding_model, [query])[0]
        _QUERY_EMBED_CACHE[embed_cache_key] = query_embedding

    if len(mentioned_entities) == 1:
        entity_name, entity_type = mentioned_entities[0]
        chunks = _query_collection(
            query=query,
            query_embedding=query_embedding,
            entity_type=entity_type,
            top_k=top_k,
            entity_name_filter=entity_name,
            diversify_by_entity=False,
        )
        return {entity_type}, chunks

    if len(mentioned_entities) >= 2:
        collected: list[RetrievedChunk] = []
        per_entity_results = max(1, top_k // len(mentioned_entities))
        for entity_name, entity_type in mentioned_entities:
            collected.extend(
                _query_collection(
                    query=query,
                    query_embedding=query_embedding,
                    entity_type=entity_type,
                    top_k=per_entity_results,
                    entity_name_filter=entity_name,
                    diversify_by_entity=False,
                )
            )
        collected.sort(key=lambda chunk: chunk.distance)
        return {entity_type for _, entity_type in mentioned_entities}, collected[:top_k]

    if len(types) == 1:
        entity_type = next(iter(types))
        chunks = _query_collection(
            query=query,
            query_embedding=query_embedding,
            entity_type=entity_type,
            top_k=top_k,
        )
        return types, chunks

    per_type_results = max(1, top_k // max(len(types), 1))
    collected: list[RetrievedChunk] = []
    for entity_type in sorted(types):
        collected.extend(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                entity_name=chunk.entity_name,
                entity_type=chunk.entity_type,
                source_url=chunk.source_url,
                distance=chunk.distance,
            )
            for chunk in _query_collection(
                query=query,
                query_embedding=query_embedding,
                entity_type=entity_type,
                top_k=per_type_results + 1,
            )
        )
    collected.sort(key=lambda chunk: chunk.distance)
    return types, collected[:top_k]
