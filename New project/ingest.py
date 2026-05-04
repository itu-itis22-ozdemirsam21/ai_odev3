from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from local_wiki_rag.service import WikiRAGService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Wikipedia pages into the local RAG system.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear the local SQLite and Chroma data before ingestion.",
    )
    args = parser.parse_args()

    service = WikiRAGService()
    results = service.ingest(reset=args.reset)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

