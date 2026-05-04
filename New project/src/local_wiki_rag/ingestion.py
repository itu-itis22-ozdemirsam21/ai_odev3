from __future__ import annotations

import re
from pathlib import Path

from .chunking import chunk_text
from .config import CHUNK_OVERLAP_WORDS, CHUNK_SIZE_WORDS, DEFAULT_EMBED_MODEL, RAW_DATA_DIR
from .entities import all_entities
from .ollama_client import OllamaClient
from .storage import (
    delete_embeddings,
    fetch_documents_summary,
    get_sqlite_connection,
    initialize_sqlite,
    replace_chunks,
    reset_sqlite,
    upsert_document,
    upsert_embeddings,
)
from .wikipedia import fetch_wikipedia_page


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return slug or "entity"


def initialize_storage(reset: bool = False) -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    initialize_sqlite()
    if reset:
        reset_sqlite()


def _existing_chunk_ids(document_id: int) -> list[str]:
    connection = get_sqlite_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT id FROM chunks WHERE document_id = ?", (document_id,))
    rows = [row["id"] for row in cursor.fetchall()]
    connection.close()
    return rows


def ingest_entities(
    reset: bool = False,
    embedding_model: str = DEFAULT_EMBED_MODEL,
) -> list[dict[str, object]]:
    initialize_storage(reset=reset)
    ollama = OllamaClient()
    results: list[dict[str, object]] = []

    for entity_name, entity_type in all_entities():
        document = fetch_wikipedia_page(entity_name)
        raw_path = RAW_DATA_DIR / f"{entity_type}_{_slugify(document.title)}.txt"
        raw_path.write_text(document.text, encoding="utf-8")

        document_id = upsert_document(
            title=document.title,
            entity_type=entity_type,
            source_url=document.source_url,
            raw_text=document.text,
            raw_path=raw_path,
        )

        previous_chunk_ids = _existing_chunk_ids(document_id)
        if previous_chunk_ids:
            delete_embeddings(previous_chunk_ids)

        chunks = chunk_text(
            document.text,
            chunk_size_words=CHUNK_SIZE_WORDS,
            overlap_words=CHUNK_OVERLAP_WORDS,
        )
        chunk_ids = [f"{entity_type}:{_slugify(document.title)}:{index}" for index in range(len(chunks))]
        replace_chunks(document_id=document_id, chunks=chunks, chunk_ids=chunk_ids)

        if chunks:
            embeddings = ollama.embed_many(embedding_model, chunks)
            metadatas = [
                {
                    "type": entity_type,
                    "entity_name": document.title,
                    "source_url": document.source_url,
                    "chunk_index": index,
                }
                for index in range(len(chunks))
            ]
            upsert_embeddings(
                ids=chunk_ids,
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadatas,
            )

        results.append(
            {
                "title": document.title,
                "type": entity_type,
                "chunk_count": len(chunks),
                "source_url": document.source_url,
            }
        )

    return results


def get_ingested_summary() -> list[dict[str, object]]:
    return [dict(row) for row in fetch_documents_summary()]
