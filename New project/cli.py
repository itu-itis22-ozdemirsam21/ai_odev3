from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from local_wiki_rag.ollama_client import OllamaError
from local_wiki_rag.service import WikiRAGService
from local_wiki_rag.wikipedia import WikipediaIngestionError


def _print_help() -> None:
    print("Commands:")
    print("- /ingest : ingest or refresh the local Wikipedia data")
    print("- /reset : rebuild the local index from scratch")
    print("- /clear : clear the current chat history")
    print("- /context on : show retrieved context after each answer")
    print("- /context off : hide retrieved context after each answer")
    print("- /stats : show document and chunk counts")
    print("- /help : show available commands")
    print("- /quit : exit the application")


def _print_context(result: dict[str, object]) -> None:
    context_items = result.get("context", [])
    if not context_items:
        print("Retrieved context: none")
        return

    print("Retrieved context:")
    for index, item in enumerate(context_items, start=1):
        print(
            f"[{index}] {item['entity_name']} ({item['entity_type']})"
        )
        print(f"    URL: {item['source_url']}")
        print(f"    Text: {item['text']}")


def main() -> None:
    service = WikiRAGService()
    show_context = False
    chat_history: list[dict[str, str]] = []

    print("Local Wikipedia RAG Chat")
    _print_help()

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input:
            continue
        if user_input == "/help":
            _print_help()
            continue
        if user_input == "/quit":
            print("Session ended.")
            break
        if user_input == "/clear":
            chat_history.clear()
            print("Chat history cleared.")
            continue
        if user_input == "/context on":
            show_context = True
            print("Retrieved context display is now ON.")
            continue
        if user_input == "/context off":
            show_context = False
            print("Retrieved context display is now OFF.")
            continue
        if user_input == "/stats":
            stats = service.stats()
            print(f"Indexed chunks: {stats['indexed_chunks']}")
            print(f"Documents: {len(stats['documents'])}")
            print(f"Chat turns in memory: {len(chat_history) // 2}")
            print(f"Show context: {'on' if show_context else 'off'}")
            continue
        if user_input in {"/ingest", "/reset"}:
            try:
                results = service.ingest(reset=user_input == "/reset")
            except (WikipediaIngestionError, OllamaError) as exc:
                print(f"Error: {exc}")
                continue
            chat_history.clear()
            print(f"Ingested {len(results)} documents.")
            continue

        try:
            result = service.ask(user_input)
        except OllamaError as exc:
            print(f"Error: {exc}")
            continue

        chat_history.append({"role": "user", "content": user_input})
        chat_history.append({"role": "assistant", "content": result["answer"]})
        print(f"Assistant: {result['answer']}")
        timings = result.get("timings", {})
        if timings:
            print(
                "Timing: "
                f"retrieve={timings.get('retrieve_ms', 0)} ms | "
                f"generate={timings.get('generate_ms', 0)} ms | "
                f"total={timings.get('total_ms', 0)} ms"
            )
        if result.get("cached"):
            print("Timing note: this answer came from the local cache.")
        if show_context:
            _print_context(result)
        elif result["context"]:
            print("Sources:")
            for item in result["context"]:
                print(f"- {item['entity_name']} ({item['entity_type']})")


if __name__ == "__main__":
    main()
