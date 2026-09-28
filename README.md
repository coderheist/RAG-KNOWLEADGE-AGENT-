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

<p align="center">
  <img src="docs/demo.gif" width="800" alt="A question streams an answer with an inline citation; the citation popover highlights the supporting sentence in the source passage">
</p>

<p align="center"><i>A real query against the running stack: the agent retrieves, grades and answers, the answer is checked against its sources, and the citation opens the passage with the supporting sentence highlighted.</i></p>

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
| + identifier pinning (retrieval-only run)² | 1.000 | 0.938 | — | — | — |
| + agentic self-correction (default) | 1.000 | 0.989 | 0.984 | 0.848 | 8.7 s |

Each row adds to the one above and is a full judged run (`jd_*` result files). ¹ Rerank helps retrieval but adds
~3.5 s p50 on CPU (p95 32 s under load), so it ships disabled; 6 of 62 cases in that run hit the Gemini free-tier
quota and are excluded from its averages. ² BM25's top hit is kept for queries containing an error code, SKU or
version (RRF was fusing exact matches out of the top 5); measured without the LLM, so judged columns are empty.
The agent row includes it. Agent vs. hybrid: refusal correctness 0.952 → 1.000, chitchat answered without
retrieval 2/7 → 7/7, at p95 5.9 s → 35 s and ≈2,160 LLM tokens per query (≈880 without the agent, from a 4-query sample; $0 on the
free tier).

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

# 🧭 Engineering decisions

**Reciprocal Rank Fusion instead of score normalisation.** Dense cosine similarity and BM25 scores live on
unrelated scales, and BM25's range shifts with the query length and the corpus statistics. Normalising and
adding them needs a weight that has to be re-tuned whenever the corpus changes. RRF (k = 60) only uses ranks, so
it has no parameter worth tuning, and it is what lifted exact-term questions (error codes, SKUs): recall@5 for
that category went from 0.583 to 0.750 with hybrid on, and overall recall@5 from 0.894 to 0.936, for about 4 ms of
extra retrieval time. The score floor and gap cut-off still run on the dense cosine score after fusion, because
that is the only score with a stable meaning.

**A local cross-encoder instead of a paid rerank API, and off by default.** Reranking is pluggable
(`RERANKER_PROVIDER`), and the local `ms-marco-MiniLM-L-6-v2` keeps queries and document text on the machine
with no per-call cost. It measurably helps (recall@5 0.936 → 0.978, MRR 0.926 → 0.967) but adds about 3.5 s p50 on
this laptop's CPU, far over the ~150 ms budget, so it ships behind `ENABLE_RERANKING`. On a GPU or with a hosted
reranker the trade changes; the flag and the eval harness make that a measurement rather than a debate.

**The retrieval loop is capped.** The agent grades what it retrieved and may rewrite the query and search again,
at most `MAX_RETRIEVAL_LOOPS = 2` times. An uncapped loop turns one bad question into unbounded LLM spend. The
cap is enforced in the graph and covered by a test in which the grader always answers "weak". The first version
also threw away a good first retrieval when a retry drifted; the final context is now chosen across all
attempts, and retries must keep identifiers such as error codes (see PROGRESS.md, Phase 4).

**Every helper step fails open.** Router, grader, groundedness check, query rewrite, tracing and metrics can each
fail (quota, timeout, malformed JSON) without failing the answer: the pipeline falls back to the plain
retrieve-and-generate path and logs the failure. The helpers use the Gemini SDK's JSON mode, not LangChain chat
models, so their tokens never leak into the streamed answer.

# 🔭 Observability

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d
```

* **Metrics:** `GET /metrics` (Prometheus): queries by route and outcome, end-to-end and per-stage latency,
  retrievals per query, LLM tokens by model and step, cost at the prices set in `LLM_PRICE_*_PER_MTOK`, embedding
  requests, retries and 429s, and ingestion throughput. Grafana at http://localhost:3001 ships a provisioned
  "RAG Agent" dashboard.
* **Tracing:** self-hosted Langfuse at http://localhost:3002 (`LANGFUSE_ENABLED=true`): one trace per query with a
  span per graph node, tagged with the active feature flags so configurations can be compared side by side.
* **Feedback loop:** thumbs up/down in the chat UI is stored by `POST /feedback` together with the retrieved chunk
  ids and the active flags. `python scripts/feedback_to_eval.py` turns thumbs-down answers into golden-set
  candidates for human review: production failure → eval case → fix → measured improvement.

![Grafana dashboard](docs/screenshots/grafana-dashboard.png)

A Langfuse trace of one agent query: the router, rewrite, retrieval (three attempts here), chunk grading,
generation and groundedness spans with timings and token counts, tagged with the active feature flags.

![Langfuse trace](docs/screenshots/langfuse-trace.png)

**Cost per query** (measured on the 62-question eval with the agent on): ≈2,040 input + 124 output LLM tokens;
$0 on the Gemini free tier. Multiply the token counts by your plan's per-token prices, or
set `LLM_PRICE_*_PER_MTOK` and read `rag_llm_cost_usd_total` from `/metrics`.

# ⚠️ Known limitations

* **Free-tier Gemini quotas shape everything.** The free tier allows about 500 requests per day per model. A full
  judged run of the agent (about 6 LLM calls per question, including the judge) fits into one day at most, and
  runs must be paced to stay under the per-minute limit. Latency numbers include those retry waits.
* **LLM calls are bounded one by one, not per request.** Each call has a 45 s timeout and the answering model
  retries at most twice, but there is no overall deadline: during a provider stall one agent query can still take
  minutes (1 of 62 eval cases exceeded 300 s). The fix is a request-level deadline that skips optional steps.
* **Ingestion is synchronous.** Upload parses, chunks, embeds and indexes inside the request; there is no
  background queue, so the UI cannot show a per-stage progress bar and very large files hold the request open.
* **No authentication or multi-tenancy.** Every user sees every document and collection. Do not expose the API
  publicly.
* **Traces cover LangChain calls in full, SDK helper calls as timings.** Router, grader and groundedness calls go
  through the Gemini SDK directly: their tokens are counted in `/metrics`, and their node spans appear in
  Langfuse, but not as separate LLM generations.
* **The golden set is synthetic** (62 questions over purpose-built documents with look-alike identifiers). It is
  good at catching regressions, not a claim about accuracy on your documents, and retrieval now reaches 1.000
  recall@5 on it, so it no longer separates retrieval changes. It needs harder cases; the feedback loop is how
  real questions get into it.

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

## Lighthouse

Production build (`npm run build && npm start`), median of three runs per page, Lighthouse 12 in headless Chrome
on the development laptop (a slow machine by Lighthouse's CPU benchmark, so the throttled mobile profile is
pessimistic).

| Profile | Page | Performance | Accessibility | Best practices | LCP | CLS |
|---|---|---|---|---|---|---|
| Desktop | /chat | 100 | 100 | 100 | 0.7 s | 0.011 |
| Desktop | /dashboard | 94 | 100 | 100 | 0.8 s | 0.005 |
| Desktop | /documents | 99 | 100 | 100 | 0.6 s | 0.005 |
| Mobile | /chat | 91 | 100 | 100 | 2.8 s | 0.025 |
| Mobile | /dashboard | 75 | 100 | 100 | 2.8 s | 0.000 |
| Mobile | /documents | 64 | 100 | 100 | 3.0 s | 0.000 |

Accessibility is 100 on every page in both profiles. Mobile performance on the dashboard and documents pages is
below the 85 target and LCP is above 2.5 s on the throttled profile; single runs vary by up to 20 points here.

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
