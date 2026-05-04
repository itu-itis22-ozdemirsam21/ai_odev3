# Product PRD: Local Wikipedia RAG Assistant

## 1. Product Overview

The product is a local, ChatGPT-style assistant that answers questions about famous people and famous places using only locally stored Wikipedia data and locally executed AI models. The system must not rely on external LLM APIs for embeddings or answer generation.

## 2. Problem Statement

Users need a lightweight question-answering system that:

- runs fully on localhost
- can retrieve trusted source material from Wikipedia
- can answer factual questions with grounded context
- can avoid unsupported answers when the data is missing

## 3. Goals

- Ingest Wikipedia pages for at least 20 famous people and 20 famous places
- Store the data locally
- Build a retrieval system over chunked documents
- Use a local language model to answer questions from retrieved context
- Provide a simple chat-style interface

## 4. Non-Goals

- web-scale search
- automatic fact-checking beyond ingested content
- multi-user deployment
- external API integration for generation
- long-term conversational memory

## 5. Users

- course instructor evaluating the assignment
- student demonstrating local RAG concepts
- developer experimenting with local retrieval and grounding workflows

## 6. Functional Requirements

### 6.1 Ingestion

- The system must fetch Wikipedia pages for predefined people and places
- The system must include the assignment's required minimum entities
- The system must store raw documents locally

### 6.2 Chunking

- The system must split long documents into smaller chunks
- The chunking strategy must handle long pages
- Overlap should be supported to preserve context continuity

### 6.3 Embedding and Storage

- The system must generate embeddings locally
- The system must store embeddings in a local vector store
- The system must store raw documents and chunk metadata in SQLite
- The system must support metadata filtering by entity type

### 6.4 Retrieval

- The system must determine whether a query targets people, places, or both
- The system must retrieve the most relevant chunks from local storage
- The routing logic may be rule-based

### 6.5 Generation

- The system must generate answers using a local language model
- The response must be grounded in retrieved context
- The system should return `I don't know.` if the answer is unsupported

### 6.6 Interface

- The system must provide a simple chat-style UI or CLI
- The system should allow users to ask questions repeatedly
- The system should optionally display retrieved chunks or sources
- The system should support clearing or resetting the system

## 7. Technical Requirements

- Language: Python
- Local model runtime: Ollama
- Embedding model: `nomic-embed-text`
- Generation model: `llama3.2:3b` by default
- Vector store: SQLite-backed local vector store
- Local metadata database: SQLite
- UI: CLI

SQLite role:

- raw Wikipedia documents
- chunk metadata
- embedding persistence

## 8. Architecture Decisions

### One Vector Store with Metadata

Decision:

- Use one SQLite-backed vector store with metadata filtering instead of two separate collections.

Reasoning:

- simpler implementation
- easier mixed-question retrieval
- less duplicate storage-management logic
- straightforward filtering by `type`
- better support for comparison-style prompts

### Paragraph-Aware Overlapping Chunking

Decision:

- Use paragraph-first chunking with overlap.

Reasoning:

- preserves semantic structure better than blind character splitting
- handles large pages
- supports more reliable retrieval context

### Ollama HTTP Integration

Decision:

- Use direct HTTP requests to the local Ollama server.

Reasoning:

- keeps the integration lightweight
- avoids depending on higher-level wrappers for core logic
- aligns with the assignment's preference for native functionality

## 9. User Stories

- As a user, I want to ask "What did Marie Curie discover?" and receive a grounded answer.
- As a user, I want to ask "Which famous place is located in Turkey?" and retrieve Hagia Sophia.
- As a user, I want the assistant to say `I don't know.` when the answer is not in the data.
- As a user, I want to inspect the retrieved context to understand why the answer was generated.

## 10. Success Metrics

- ingestion succeeds for all required entities
- questions about required entities return relevant answers
- failure-case questions return `I don't know.` or clearly indicate insufficient support
- project can be run locally by following the README only

Minimal grading rubric:

- Retrieval: at least one relevant chunk is returned for a known entity.
- Groundedness: answers are supported by retrieved context.
- Refusal: unsupported questions should not produce fabricated answers.
- Mixed routing: mixed queries search both categories when required.
- Comparison: comparison prompts include context for both entities.

## 11. Risks and Tradeoffs

- Smaller local models are cheaper to run but less accurate
- Rule-based query routing is simple but not always robust
- A native SQLite vector store is easier to explain but slower than specialized vector databases
- Wikipedia extracts may contain noisy or uneven formatting
- Changing the embedding model requires full re-ingestion because vector outputs must remain consistent

## 12. Future Enhancements

- streaming token output
- citations with highlighted chunk spans
- response caching
- better reranking
- multi-turn memory
- evaluation harness for benchmark questions
