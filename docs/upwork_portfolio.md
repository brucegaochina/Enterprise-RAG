# Upwork portfolio entry

## Title (max 70 chars)

Enterprise RAG: AI Chat over Company Documents with Cited Answers

## Description

Built a production-style Retrieval-Augmented Generation (RAG) system that lets employees ask questions about internal documents and get accurate answers with clickable citations to the source files.

- Ingests PDF, DOCX, Markdown and TXT, with layout-aware parsing that keeps tables and page numbers
- Structure-aware chunking and embeddings stored in PostgreSQL + pgvector
- Hybrid retrieval: vector similarity plus full-text search, fused with Reciprocal Rank Fusion
- Conversational follow-ups via automatic query rewriting
- Streaming answers that cite their sources; every citation opens the original document with the passage highlighted
- Full transparency: relevance scores, retrieval steps, latency and the exact prompt
- Retrieval evaluation (Hit@k, MRR) to measure and improve answer quality
- Works with OpenAI, Azure OpenAI or any OpenAI-compatible model, including self-hosted

Tech: Python, FastAPI, PostgreSQL, pgvector, OpenAI API, JavaScript

## Skills to tag

Retrieval Augmented Generation · LLM · OpenAI API · FastAPI · Python · PostgreSQL · pgvector · Vector Database · Chatbot Development · AI Development

## Media order

1. Video (2–3 minutes, follow the demo script in README.md)
2. docs/screenshots/02_answer_supporting_content.png (thumbnail)
3. docs/screenshots/04_citation_highlight.png
4. docs/screenshots/03_thought_process.png
5. docs/screenshots/07_retrieval_lab.png
6. docs/screenshots/05_knowledge_base.png
