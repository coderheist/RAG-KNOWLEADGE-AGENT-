<div align="center">

# 🚀 Production RAG Agent

### Enterprise-Grade Retrieval-Augmented Generation (RAG) Platform

Build AI-powered knowledge assistants capable of ingesting, indexing, retrieving, and reasoning over your documents using **Google Gemini**, **LangGraph**, **FastAPI**, **Next.js**, **PostgreSQL**, and **Qdrant**.

<p>

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Production-009688?logo=fastapi)
![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?logo=postgresql)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20Database-red)
![Google Gemini](https://img.shields.io/badge/Google-Gemini-orange?logo=google)

</p>

</div>

---

# 📊 Results

Every retrieval or generation change is measured on a 62-case golden set (`backend/evals/datasets/golden_v1.jsonl`)
through the real `/query` endpoint. Numbers come from result files in `backend/evals/results/`; rows fill in as each
change is measured, and a change that does not help is reported as such.

| Configuration | recall@5 | MRR | faithfulness | citation acc. | p50 latency |
|---|---|---|---|---|---|
| Baseline (dense only) | 0.745 | 0.670 | 0.967 | 0.700 | 3.9 s |
| + query rewriting | 0.894 | 0.846 | 0.952 | 0.833 | 3.1 s |
| + hybrid search (default) | 0.936 | 0.926 | 0.968 | 0.841 | 3.2 s |
| + cross-encoder rerank (off by default)¹ | 0.978 | 0.967 | 0.982 | 0.822 | 6.9 s |
| + agentic self-correction | — | — | — | — | — |

Each row adds to the one above and is a full judged run (`jd_*` result files). ¹ Rerank helps retrieval but adds
~3.5 s p50 on CPU (p95 32 s under load), so it ships disabled; 6 of 62 cases in that run hit the Gemini free-tier
quota and are excluded from its averages.

Baseline weak spots (recall@5 by category): exact terms 0.583, follow-up questions 0.300, versus 1.000 for factual and
multi-hop lookups. Those two categories are what the next changes target. Corpus: ~90 chunks of synthetic documents
with deliberately look-alike identifiers (near-identical error codes and SKUs), so retrieval is not trivially easy.

---

# 📖 Overview

Production RAG Agent is a full-stack enterprise-ready Retrieval-Augmented Generation (RAG) system designed to build intelligent AI assistants over private documents.

Instead of relying only on an LLM's internal knowledge, the application retrieves relevant information from your uploaded documents using semantic search, injects that context into the prompt, and generates grounded responses with source citations.

The project emphasizes production engineering practices including resilient document ingestion, deterministic chunking, duplicate detection, retry handling, crash recovery, and scalable vector search.

---

# ⭐ Highlights

- Enterprise-grade RAG Architecture
- Multi-format Document Ingestion
- Google Gemini Integration
- LangGraph-based AI Pipeline
- FastAPI Backend
- Next.js + TypeScript Frontend
- PostgreSQL Metadata Storage
- Qdrant Vector Database
- Adaptive Semantic Chunking
- Duplicate Document Detection
- Resume-safe Indexing
- Streaming AI Chat
- Source Citations
- Docker Deployment
- Production Health Monitoring

---

# ✨ Features

## 📂 Document Processing

Supports uploading and indexing:

- PDF
- DOCX
- PPTX
- XLSX
- CSV
- TXT
- Markdown

Each uploaded document is automatically:

- Validated
- Parsed
- Chunked
- Embedded
- Indexed
- Stored

---

## 🧠 Adaptive Semantic Chunking

Production-friendly chunking pipeline featuring:

- Recursive chunk splitting
- Configurable chunk size
- Chunk overlap
- Deterministic Chunk IDs
- Duplicate detection
- Resume interrupted indexing

---

## 🤖 Retrieval-Augmented Generation

Instead of sending the whole document to the LLM:

1. User asks a question.
2. Semantic search retrieves relevant chunks.
3. LangGraph constructs context.
4. Google Gemini generates grounded answers.
5. Sources are returned alongside the response.

---

## ⚡ Resilient Embedding Pipeline

Designed to work reliably with external AI providers.

Features include:

- Dynamic Batch Sizing
- Exponential Backoff
- Retry with Jitter
- Adaptive Batch Reduction
- Concurrency Control
- Duplicate-safe Processing

> **Note:** When using the Google Gemini Free Tier, very large documents may require several minutes to finish embedding due to provider quota limits. Background asynchronous processing is planned in a future release.

---

## 💬 AI Chat

Supports:

- Conversational RAG
- Streaming Responses
- Markdown Rendering
- Code Blocks
- Copy Response
- Source Citations

---

## 📁 Document Management

- Upload Documents
- Delete Documents
- Duplicate Detection
- Already Indexed Detection
- Chunk Statistics
- Document Metadata

---

## 📊 Dashboard

Real-time monitoring for:

- Backend API
- Google Gemini
- PostgreSQL
- Qdrant
- Document Count
- Chunk Count
- Storage Usage

---

# 🏗 Architecture

```
                     User
                       │
                       ▼
             Next.js Frontend
                       │
             REST / Streaming API
                       │
                       ▼
               FastAPI Backend
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
 Google Gemini     PostgreSQL      Qdrant
      │             Metadata     Vector Store
      └───────────────┬───────────────┘
                      ▼
                 LangGraph RAG
```

## Agent graph

Generated from the compiled LangGraph (`_compile_graph().get_graph().draw_mermaid()`). Dashed edges are
conditional. The router sends chitchat and clarification requests straight to `direct_response` with no retrieval;
`grade_chunks` sends weak results back to `rewrite_query` for at most `MAX_RETRIEVAL_LOOPS` retries; `check_grounded`
appends a visible caveat when the answer is not supported by the retrieved sources. Each step is behind a flag
(`ENABLE_AGENTIC_LOOP`, `ENABLE_GROUNDEDNESS_CHECK`, `ENABLE_VERIFIED_CITATIONS`) and fails open.

```mermaid
graph TD;
	__start__([start]) --> router;
	router -.-> rewrite_query;
	router -.-> direct_response;
	rewrite_query --> retrieve;
	retrieve -.-> grade_chunks;
	retrieve -.-> generate;
	grade_chunks -.-> rewrite_query;
	grade_chunks -.-> generate;
	generate --> check_grounded;
	check_grounded --> save_history;
	direct_response --> save_history;
	save_history --> __end__([end]);
```

---

# ⚙ Technology Stack

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS

## Backend

- FastAPI
- LangGraph
- SQLAlchemy
- Pydantic

## AI

- Google Gemini
- Semantic Embeddings
- Retrieval-Augmented Generation

## Databases

- PostgreSQL
- Qdrant Vector Database

## DevOps

- Docker
- Docker Compose

---

# 📸 Application Preview

Captured from the production build (`npm run build && npm start`) in light and dark mode; mobile shots at 390 px.

| | Light | Dark |
|---|---|---|
| Dashboard | ![Dashboard, light](docs/screenshots/dashboard-desktop-light.png) | ![Dashboard, dark](docs/screenshots/dashboard-desktop-dark.png) |
| Documents | ![Documents, light](docs/screenshots/documents-desktop-light.png) | ![Documents, dark](docs/screenshots/documents-desktop-dark.png) |
| Chat | ![Chat, light](docs/screenshots/chat-desktop-light.png) | ![Chat, dark](docs/screenshots/chat-desktop-dark.png) |

<p>
<img src="docs/screenshots/dashboard-mobile-light.png" width="200" alt="Dashboard on mobile">
<img src="docs/screenshots/documents-mobile-dark.png" width="200" alt="Documents on mobile, dark">
<img src="docs/screenshots/chat-mobile-light.png" width="200" alt="Chat on mobile">
</p>

---

# 🚀 Getting Started

## Clone Repository

```bash
git clone https://github.com/rounakkumarsah/Production-RAG-Agent.git

cd Production-RAG-Agent
```

---

## Configure Environment

Create:

```
.env

backend/.env
```

Copy values from:

```
.env.example

backend/.env.example
```

Configure:

- Google Gemini API Key
- PostgreSQL
- Qdrant

---

## Start Backend

```bash
cd backend

docker compose up --build
```

---

## Start Frontend

```bash
cd ..

npm install

npm run dev
```

---

Open:

Frontend

```
http://localhost:3000
```

Backend

```
http://localhost:8000
```

Swagger API

```
http://localhost:8000/docs
```

---

# 📂 Project Structure

```
Production-RAG-Agent/

├── app/
├── backend/
│   ├── app/
│   ├── services/
│   ├── api/
│   ├── docker-compose.yml
│   └── requirements.txt
│
├── components/
├── lib/
├── public/
├── package.json
├── next.config.ts
└── README.md
```

---

# 🔥 Production Engineering Features

✅ Deterministic Chunk IDs

✅ Duplicate Document Detection

✅ Resume Interrupted Indexing

✅ Adaptive Batch Embedding

✅ Exponential Backoff & Retry

✅ Dynamic Batch Reduction

✅ Similarity Threshold Filtering

✅ Streaming Responses

✅ Health Monitoring

✅ Dockerized Deployment

---

# 📈 Roadmap

- [ ] Background Workers
- [ ] Async Upload Queue
- [ ] Redis Cache
- [ ] User Authentication
- [ ] Multi-Tenant Support
- [ ] Role Based Access Control
- [ ] Observability Dashboard
- [ ] Kubernetes Deployment
- [ ] CI/CD Pipeline
- [ ] Automated Evaluation Suite

---

# 🎯 Learning Objectives

This project demonstrates practical experience with:

- Retrieval-Augmented Generation (RAG)
- AI Engineering
- Vector Databases
- Semantic Search
- LangGraph Workflows
- Google Gemini APIs
- Production FastAPI Development
- Full Stack AI Applications
- Docker Deployment
- Enterprise Software Architecture

---

# 🤝 Contributing

Contributions are welcome!

If you'd like to improve the project:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Open a Pull Request

---

# 📄 License

This project is licensed under the MIT License.

---

# 👨‍💻 Author

## Rounak Kumar Sah

**AI Automation Engineer | AI Agent Developer | GenAI Engineer**

### Tech Stack

- Python
- FastAPI
- LangGraph
- Next.js
- TypeScript
- PostgreSQL
- Qdrant
- Docker
- Google Gemini
- n8n Automation

---

<div align="center">

⭐ If you found this project useful, please consider giving it a Star.

</div>
