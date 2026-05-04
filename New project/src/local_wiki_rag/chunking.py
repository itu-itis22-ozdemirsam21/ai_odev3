from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_long_paragraph(paragraph: str) -> list[str]:
    sentence_candidates = re.split(r"(?<=[.!?])\s+", paragraph.strip())
    parts = [part.strip() for part in sentence_candidates if part.strip()]
    return parts if parts else [paragraph.strip()]


def _chunk_from_units(units: list[str], chunk_size_words: int, overlap_words: int) -> list[str]:
    chunks: list[str] = []
    current_words: list[str] = []

    for unit in units:
        words = unit.split()
        if not words:
            continue

        if len(words) > chunk_size_words:
            if current_words:
                chunks.append(" ".join(current_words).strip())
                current_words = current_words[-overlap_words:] if overlap_words else []

            start = 0
            while start < len(words):
                end = min(start + chunk_size_words, len(words))
                chunk_words = words[start:end]
                chunks.append(" ".join(chunk_words).strip())
                if end == len(words):
                    current_words = chunk_words[-overlap_words:] if overlap_words else []
                    break
                start = max(end - overlap_words, start + 1)
            continue

        projected_size = len(current_words) + len(words)
        if current_words and projected_size > chunk_size_words:
            chunks.append(" ".join(current_words).strip())
            current_words = current_words[-overlap_words:] if overlap_words else []

        current_words.extend(words)

    if current_words:
        chunks.append(" ".join(current_words).strip())

    return [chunk for chunk in chunks if chunk]


def chunk_text(text: str, chunk_size_words: int, overlap_words: int) -> list[str]:
    cleaned = normalize_text(text)
    if not cleaned:
        return []

    paragraphs = [part.strip() for part in cleaned.split("\n\n") if part.strip()]
    units: list[str] = []
    for paragraph in paragraphs:
        words = paragraph.split()
        if len(words) > chunk_size_words:
            units.extend(_split_long_paragraph(paragraph))
        else:
            units.append(paragraph)

    return _chunk_from_units(units, chunk_size_words, overlap_words)

