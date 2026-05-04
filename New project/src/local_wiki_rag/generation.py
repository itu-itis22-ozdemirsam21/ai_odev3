from __future__ import annotations

import re

from .config import DEFAULT_LLM_MODEL, MAX_CONTEXT_CHUNKS, MAX_SENTENCES_PER_CHUNK
from .ollama_client import OllamaClient
from .retrieval import RetrievedChunk


PROMPT_TEMPLATE = """You are a local Wikipedia assistant.
Answer the user's question using only the retrieved context below.
If the context does not contain the answer, respond exactly with: I don't know.
Do not use outside knowledge.
When the user asks for a comparison, compare only what appears in the context.

Question:
{query}

Context:
{context}

Answer:"""

UNKNOWN_RESPONSES = {
    "i don't know",
    "i don't know.",
    "i do not know",
    "i do not know.",
}


def _rank_sentences_for_query(query: str, text: str, limit: int) -> list[str]:
    sentences = _split_sentences(text)
    if not sentences:
        return []

    query_tokens = {
        token
        for token in re.findall(r"[a-zA-Z]+", query.lower())
        if len(token) > 2 and token not in {"the", "and", "for", "with", "this", "that", "from"}
    }

    scored: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(sentences):
        sentence_tokens = set(re.findall(r"[a-zA-Z]+", sentence.lower()))
        overlap = len(query_tokens & sentence_tokens)
        lead_bonus = 1 if index == 0 else 0
        scored.append((overlap + lead_bonus, index, sentence))

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [sentence for _, _, sentence in scored[:limit]]
    ordered = [sentence for sentence in sentences if sentence in selected]
    return ordered[:limit]


def build_context(query: str, chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No relevant context was retrieved."

    parts = []
    for index, chunk in enumerate(chunks[:MAX_CONTEXT_CHUNKS], start=1):
        ranked_sentences = _rank_sentences_for_query(query, chunk.text, MAX_SENTENCES_PER_CHUNK)
        snippet = " ".join(ranked_sentences) if ranked_sentences else chunk.text
        parts.append(
            f"[Source {index}] {chunk.entity_name} ({chunk.entity_type})\n"
            f"URL: {chunk.source_url}\n"
            f"{snippet}"
        )
    return "\n\n".join(parts)


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def _is_unknown_response(response: str) -> bool:
    return response.strip().lower() in UNKNOWN_RESPONSES


def _extractive_fallback(query: str, chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "I don't know."

    lead_chunk = chunks[0]
    lead_sentences = _split_sentences(lead_chunk.text)
    lowered_query = query.strip().lower()

    if lowered_query.startswith(("who is", "who was", "what is", "what was", "where is", "where was", "which")):
        if len(lead_sentences) >= 2:
            return " ".join(lead_sentences[:2]).strip()
        if lead_sentences:
            return lead_sentences[0].strip()

    query_tokens = {
        token
        for token in re.findall(r"[a-zA-Z]+", lowered_query)
        if len(token) > 2 and token not in {"the", "and", "for", "with", "this", "that", "from"}
    }
    for chunk in chunks:
        for sentence in _split_sentences(chunk.text):
            sentence_tokens = set(re.findall(r"[a-zA-Z]+", sentence.lower()))
            if query_tokens & sentence_tokens:
                return sentence.strip()

    if lead_sentences:
        return lead_sentences[0].strip()
    return lead_chunk.text.strip() or "I don't know."


def generate_answer(
    query: str,
    chunks: list[RetrievedChunk],
    llm_model: str = DEFAULT_LLM_MODEL,
) -> str:
    if not chunks:
        return "I don't know."

    prompt = PROMPT_TEMPLATE.format(query=query.strip(), context=build_context(query, chunks))
    ollama = OllamaClient()
    response = ollama.generate(llm_model, prompt)
    if not response or _is_unknown_response(response):
        return _extractive_fallback(query, chunks)
    return response
