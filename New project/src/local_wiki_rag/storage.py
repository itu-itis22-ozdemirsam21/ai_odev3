from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

from .config import SQLITE_PATH


def ensure_directories() -> None:
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_sqlite_connection() -> sqlite3.Connection:
    ensure_directories()
    connection = sqlite3.connect(SQLITE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_sqlite() -> None:
    connection = get_sqlite_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL UNIQUE,
            entity_type TEXT NOT NULL,
            source_url TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            raw_path TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            word_count INTEGER NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding_json TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_documents_entity_type
        ON documents (entity_type)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chunks_document_id
        ON chunks (document_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_embeddings_entity_type
        ON embeddings (entity_type)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_embeddings_entity_name
        ON embeddings (entity_name)
        """
    )
    connection.commit()
    connection.close()


def reset_sqlite() -> None:
    connection = get_sqlite_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM embeddings")
    cursor.execute("DELETE FROM chunks")
    cursor.execute("DELETE FROM documents")
    connection.commit()
    connection.close()


def upsert_document(
    title: str,
    entity_type: str,
    source_url: str,
    raw_text: str,
    raw_path: Path,
) -> int:
    connection = get_sqlite_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO documents (title, entity_type, source_url, raw_text, raw_path)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(title) DO UPDATE SET
            entity_type=excluded.entity_type,
            source_url=excluded.source_url,
            raw_text=excluded.raw_text,
            raw_path=excluded.raw_path
        """,
        (title, entity_type, source_url, raw_text, str(raw_path)),
    )
    connection.commit()
    cursor.execute("SELECT id FROM documents WHERE title = ?", (title,))
    row = cursor.fetchone()
    connection.close()
    if row is None:
        raise RuntimeError(f"Could not look up document id for {title}.")
    return int(row["id"])


def replace_chunks(document_id: int, chunks: list[str], chunk_ids: list[str]) -> None:
    connection = get_sqlite_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
    rows = [
        (chunk_id, document_id, index, chunk, len(chunk.split()))
        for index, (chunk_id, chunk) in enumerate(zip(chunk_ids, chunks))
    ]
    cursor.executemany(
        """
        INSERT INTO chunks (id, document_id, chunk_index, chunk_text, word_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.commit()
    connection.close()


def fetch_documents_summary() -> list[sqlite3.Row]:
    connection = get_sqlite_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            d.title,
            d.entity_type,
            d.source_url,
            COUNT(c.id) AS chunk_count
        FROM documents d
        LEFT JOIN chunks c ON c.document_id = d.id
        GROUP BY d.id
        ORDER BY d.entity_type, d.title
        """
    )
    rows = cursor.fetchall()
    connection.close()
    return rows


def upsert_embeddings(
    ids: list[str],
    documents: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any]],
) -> None:
    connection = get_sqlite_connection()
    cursor = connection.cursor()
    rows = []
    for item_id, document, embedding, metadata in zip(ids, documents, embeddings, metadatas):
        rows.append(
            (
                item_id,
                metadata["type"],
                metadata["entity_name"],
                metadata["source_url"],
                metadata["chunk_index"],
                document,
                json.dumps(embedding),
            )
        )
    cursor.executemany(
        """
        INSERT OR REPLACE INTO embeddings (
            id,
            entity_type,
            entity_name,
            source_url,
            chunk_index,
            chunk_text,
            embedding_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.commit()
    connection.close()


def delete_embeddings(ids: list[str]) -> None:
    if not ids:
        return
    connection = get_sqlite_connection()
    cursor = connection.cursor()
    placeholders = ",".join("?" for _ in ids)
    cursor.execute(f"DELETE FROM embeddings WHERE id IN ({placeholders})", ids)
    connection.commit()
    connection.close()


def collection_count() -> int:
    connection = get_sqlite_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) AS count FROM embeddings")
    row = cursor.fetchone()
    connection.close()
    return int(row["count"]) if row else 0


def fetch_embeddings(entity_type: Optional[str] = None) -> list[sqlite3.Row]:
    connection = get_sqlite_connection()
    cursor = connection.cursor()
    if entity_type:
        cursor.execute(
            """
            SELECT id, entity_type, entity_name, source_url, chunk_index, chunk_text, embedding_json
            FROM embeddings
            WHERE entity_type = ?
            """,
            (entity_type,),
        )
    else:
        cursor.execute(
            """
            SELECT id, entity_type, entity_name, source_url, chunk_index, chunk_text, embedding_json
            FROM embeddings
            """
        )
    rows = cursor.fetchall()
    connection.close()
    return rows
