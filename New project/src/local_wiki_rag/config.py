from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
SQLITE_PATH = DATA_DIR / "wiki_rag.db"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.2:3b")
DEFAULT_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"

CHUNK_SIZE_WORDS = int(os.getenv("CHUNK_SIZE_WORDS", "220"))
CHUNK_OVERLAP_WORDS = int(os.getenv("CHUNK_OVERLAP_WORDS", "45"))
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "3"))
MAX_CONTEXT_CHUNKS = int(os.getenv("MAX_CONTEXT_CHUNKS", "3"))
MAX_SENTENCES_PER_CHUNK = int(os.getenv("MAX_SENTENCES_PER_CHUNK", "2"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "90"))
