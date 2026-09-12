# 🎯 Resume Screener AI

An intelligent, enterprise-ready, multi-tenant resume screening and candidate ranking platform. Built with **Django REST Framework**, **pgvector**, **Celery**, **HuggingFace Sentence Transformers**, and **Groq LLM** (`openai/gpt-oss-120b`).

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg?logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.1-092E20.svg?logo=django&logoColor=white)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.18-red.svg)](https://django-rest-framework.org)
[![pgvector](https://img.shields.io/badge/pgvector-0.5.0-336791.svg?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Celery](https://img.shields.io/badge/Celery-5.6-37814A.svg?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Groq](https://img.shields.io/badge/Groq-API-F55036.svg)](https://groq.com)
[![Package Manager](https://img.shields.io/badge/uv-fast_packaging-purple.svg)](https://github.com/astral-sh/uv)

---

## 📑 Table of Contents

- [Overview](#-overview)
- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Screening & Ranking Pipeline](#-screening--ranking-pipeline)
  - [1. Ingestion & Semantic Chunking](#1-ingestion--semantic-chunking)
  - [2. Dense Vector Retrieval (HNSW)](#2-dense-vector-retrieval-hnsw)
  - [3. JIT Profile Extraction via Groq LLM](#3-jit-profile-extraction-via-groq-llm)
  - [4. Composite Scoring Formulation](#4-composite-scoring-formulation)
  - [5. Recruiter Dossier Generation](#5-recruiter-dossier-generation)
- [Interactive RAG Chat Assistant (Phase 6)](#-interactive-rag-chat-assistant-phase-6)
  - [1. Job-Scoped Dense Vector Retrieval](#1-job-scoped-dense-vector-retrieval)
  - [2. Three-Tier Confidence Gate & Borderline Handling](#2-three-tier-confidence-gate--borderline-handling)
  - [3. Sliding Context Window & Prompt Engineering](#3-sliding-context-window--prompt-engineering)
  - [4. Real-Time Token Streaming via SSE](#4-real-time-token-streaming-via-sse)
  - [5. Resilient Turn Persistence](#5-resilient-turn-persistence)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Configuration](#environment-configuration)
  - [Installation with `uv`](#installation-with-uv)
  - [Database Setup & Migrations](#database-setup--migrations)
  - [Running the Services](#running-the-services)
- [API Reference](#-api-reference)
  - [Authentication](#authentication)
  - [Jobs API](#jobs-api)
  - [Resumes API](#resumes-api)
  - [Applications API](#applications-api)
  - [Chat Sessions & Streaming API](#chat-sessions--streaming-api)
- [Testing & Quality Assurance](#-testing--quality-assurance)
- [Roadmap](#-roadmap)
- [License](#-license)

---

## 💡 Overview

Modern hiring teams receive hundreds of resumes per job posting. Traditional keyword filtering misses qualified candidates who phrase their experience differently, while brute-force LLM evaluation of every resume is cost-prohibitive and slow.

**Resume Screener AI** provides a complete end-to-end recruitment intelligence engine:

1. **Sub-second Vector Search:** Leverages PostgreSQL `pgvector` with HNSW indexing on dense 384-dimensional embeddings to narrow hundreds of candidates down to the top relevant applicants.
2. **Just-In-Time (JIT) LLM Analysis:** Executes structured Pydantic extraction on qualified candidates via Groq's high-speed inference engine (`openai/gpt-oss-120b`).
3. **Multi-Factor Scoring:** Combines semantic similarity (65%), exact skill alignment (20%), and years of experience (15%) into an explainable composite score with tailored recruiter dossiers.
4. **Interactive Multi-Tenant RAG Chat Assistant:** Empowers recruiters to ask ad-hoc questions about applicants for any job, featuring job-scoped vector retrieval, deterministic similarity pre-filtering, borderline confidence prompt injection, and real-time Server-Sent Events (SSE) token streaming via `AsyncGroq`.

---

## 🏗 System Architecture

```mermaid
flowchart TD
    subgraph Client["Client Applications"]
        FE["Next.js Web Frontend"]
        EXT["API Consumers / ATS / Postman"]
    end

    subgraph API["Django REST Framework & Async Streaming"]
        AUTH["JWT Authentication & Blacklisting (Redis)"]
        JOBS_API["Job Postings ViewSet"]
        RES_API["Resume Upload ViewSet (Batch/Single)"]
        APP_API["Applications ViewSet"]
        SESS_API["Chat Sessions ViewSet (CRUD + Messages)"]
        STREAM_API["chat_stream_view (Async SSE Relay)"]
    end

    subgraph Worker["Celery Distributed Workers"]
        T_INGEST["process_resume<br/>(PyMuPDF + Token Overlap Chunking)"]
        T_EMBED["embed_chunks / embed_job<br/>(all-MiniLM-L6-v2)"]
        T_RECOMP["recompute_job_rankings<br/>(Vector Retrieval + Aggregation)"]
        T_CHORD["Chord: extract_resume_profile<br/>(Groq LLM + Pydantic)"]
        T_SCORE["finalize_scoring & dossiers<br/>(Weighted Composite Formula)"]
    end

    subgraph ChatEngine["RAG Chat Intelligence Engine"]
        RETRIEVE["fetch_candidate_chunks_for_session<br/>(Job & Tenant Scoped pgvector Search)"]
        GATE{"Deterministic Confidence Gate"}
        PROMPT["build_chat_prompt_messages<br/>(Sliding N=10 History + Caution Clause)"]
        ASYNC_GROQ["AsyncGroq Client<br/>(openai/gpt-oss-120b Streaming)"]
    end

    subgraph Storage["Databases & Infrastructure"]
        PG[("Neon Serverless PostgreSQL<br/>+ pgvector (HNSW Index)")]
        REDIS[("Redis<br/>(Broker, Cache, JWT JTI Blocklist)")]
    end

    FE -->|Bearer Token| API
    EXT -->|Bearer Token| API
    API --> AUTH
    AUTH <--> REDIS
    API --> Storage
    API -->|delay_on_commit| Worker
    Worker <--> Storage
    Worker -->|Inference| GROQ["Groq LLM Cloud (gpt-oss-120b)"]

    STREAM_API --> RETRIEVE
    RETRIEVE <--> PG
    RETRIEVE --> GATE
    GATE -->|distance >= -0.20| DECLINE["Instant Canned Decline (0 LLM Cost)"]
    GATE -->|-0.35 <= distance < -0.20| PROMPT_BORDERLINE["Inject Low-Confidence Caution Clause"]
    GATE -->|distance < -0.35| PROMPT_NORMAL["Normal Context Prompt"]
    PROMPT_BORDERLINE --> PROMPT
    PROMPT_NORMAL --> PROMPT
    PROMPT --> ASYNC_GROQ
    ASYNC_GROQ -->|Token Deltas (text/event-stream)| STREAM_API
    DECLINE -->|Canned Event| STREAM_API
    STREAM_API -->|Persist Turns| PG
```

---

## ✨ Key Features

- 🏢 **Strict Multi-Tenancy:** Each company/tenant manages its own jobs, applicant pools, and chat sessions with database-level isolation.
- 💬 **Interactive Job-Scoped RAG Chat:** Recruiters can query applicant resumes conversationally for any specific job with real-time SSE streaming.
- 🛡️ **Three-Tier Deterministic Confidence Gate:** Prevents hallucinations and eliminates unnecessary LLM costs:
  - $d \ge -0.20$: Instant zero-cost decline string (`CANNED_DECLINE`) without invoking Groq.
  - $-0.35 \le d < -0.20$: Borderline band — proceeds to Groq with an injected low-confidence caution clause.
  - $d < -0.35$: Confident match — standard LLM inference.
- ⚡ **Low-Latency Streaming:** Real-time token relay directly from `AsyncGroq` using Server-Sent Events (`text/event-stream`).
- 📜 **Sliding-Window Dialogue History:** Retains $N=10$ chronologically ordered message history per session with partial persist guards on client disconnect.
- 🔐 **Hardened Authentication:** Argon2 password hashing, JWT access/refresh token rotation, and Redis-backed JTI revocation upon logout.
- 📂 **Flexible Resume Ingestion:** Supports single and batch PDF resume uploads with automatic mime-type validation and file size constraints (10MB limit).
- 🧩 **Token-Aware Chunking:** Uses HuggingFace tokenizers with sliding-window overlap (200 tokens window, 20 tokens overlap) to preserve semantic context across page and paragraph boundaries.
- ⚡ **High-Performance Vector Search:** pgvector HNSW indexing (`vector_ip_ops`, $m=16$, $ef=64$) for sub-second retrieval over thousands of resume chunks.
- 🤖 **Structured LLM Extraction:** Strict schema enforcement via Pydantic (`extra="forbid"`) running on Groq (`openai/gpt-oss-120b`) for zero-hallucination skill and experience parsing.
- 📊 **Explainable Composite Scoring:** Transparent scoring weights combining semantic relevance, hard skill matching, and career seniority.
- 📝 **Automated Recruiter Dossiers:** Generates concise executive summaries, key candidate strengths, and qualification gaps for shortlisted applicants.
- 🧪 **Ephemeral Neon Database Testing:** CI/test scripts dynamically spin up and tear down isolated Neon PostgreSQL branches for production-identical test runs.

---

## ⚙️ Screening & Ranking Pipeline

### 1. Ingestion & Semantic Chunking

When a PDF resume is uploaded:

- **PyMuPDF (`fitz`)** extracts raw textual content.
- The text is tokenized using `AutoTokenizer` from `sentence-transformers/all-MiniLM-L6-v2`.
- A sliding window splits the document into chunks of **200 tokens with a 20-token overlap**.
- Each chunk is embedded into a **384-dimensional normalized vector** and stored in `ResumeChunk` with an HNSW index.

### 2. Dense Vector Retrieval (HNSW)

When candidate ranking is triggered:

- The job description embedding is compared against candidate resume chunks using **Max Inner Product** (cosine similarity on normalized vectors).
- An over-fetch factor ($k = \text{head\_count} \times 5$) retrieves top candidate chunks scoped strictly to the tenant's applicants.
- **Top-2 Mean Aggregation:** To avoid single-paragraph bias, each resume's retrieval score is computed as the average distance of its **top 2 best-matching chunks**:
  $$\text{Retrieval Score} = \frac{d_1 + d_2}{2}$$

### 3. JIT Profile Extraction via Groq LLM

Instead of spending LLM tokens on every applicant:

- Extraction runs only on candidates qualifying in the top candidate pool ($2 \times \text{head\_count}$).
- A Celery **`chord`** parallelizes extraction across candidate resumes using Groq's high-throughput `openai/gpt-oss-120b` endpoint:
  ```json
  {
    "skills": ["Python", "Django", "PostgreSQL", "Docker", "Celery"],
    "experience_years": 5
  }
  ```
- Guaranteed type safety through Pydantic strict JSON schema validation.

### 4. Composite Scoring Formulation

The `finalize_scoring` task evaluates every applicant using a deterministic composite formula:

$$\text{Final Score} = (65 \times S_{\text{retrieval}}) + (20 \times S_{\text{skills}}) + (15 \times S_{\text{experience}})$$

Where:

- **$S_{\text{retrieval}}$**: Normalized cosine similarity score (range $[0, 1]$).
- **$S_{\text{skills}}$**: Exact matched skills ratio:
  $$S_{\text{skills}} = \frac{|\text{Candidate Skills} \cap \text{Required Skills}|}{|\text{Required Skills}|}$$
- **$S_{\text{experience}}$**: Seniority alignment ratio:
  $$S_{\text{experience}} = \min\left(1.0, \frac{\text{Candidate Experience Years}}{\text{Required Experience Years}}\right)$$

### 5. Recruiter Dossier Generation

For candidates within the final `head_count`:

- An asynchronous task queries Groq with the match breakdown (matched skills, missing skills, vector distance, experience delta).
- Produces an executive dossier containing:
  - **Summary**: Recruiter-focused neutral overview.
  - **Strengths**: Specific candidate advantages relative to the role.
  - **Gaps**: Missing requirements or areas needing interview probing.

---

## 💬 Interactive RAG Chat Assistant (Phase 6)

The interactive chat assistant enables hiring teams to converse directly with candidate resume data for any specific job posting in real time. Rather than simple keyword matching, the assistant grounds every answer in the actual retrieved candidate resume chunks while enforcing strict multi-tenant boundaries.

### 1. Job-Scoped Dense Vector Retrieval
- **Query Embedding**: The incoming recruiter query is embedded using `sentence-transformers/all-MiniLM-L6-v2` into a 384-dimensional normalized vector.
- **Tenant & Job Isolation**: A `pgvector` inner product search (`<#>`) queries `ResumeChunk` objects where:
  ```sql
  WHERE resume__applications__job_id = session.job_id
    AND resume__company_id = session.company_id
  ```
- **Aggregation**: Retrieves the highest-matching chunks associated strictly with candidates who applied for that specific job posting.

### 2. Three-Tier Confidence Gate & Borderline Handling
To eliminate LLM hallucinations on out-of-scope queries and prevent unnecessary LLM expenses, retrieval relevance is classified into three deterministic bands based on top result distance ($d = -\text{dot\_product}$):

| Band | Top Chunk Distance ($d$) | Action | LLM Call Made? |
| :--- | :--- | :--- | :---: |
| **`decline`** | $d \ge -0.20$ (or empty) | Immediately return plain string constant (`CANNED_DECLINE`) | ❌ No |
| **`borderline`** | $-0.35 \le d < -0.20$ | Inject low-confidence caution clause into system prompt | ✅ Yes |
| **`confident`** | $d < -0.35$ | Standard system prompt with candidate chunk context | ✅ Yes |

- **Caution Clause Injected on Borderline Queries**:
  > *"Retrieval confidence for this query was low. If the provided context is insufficient to answer accurately, decline and briefly explain why rather than guessing."*
- **Preserved Economics & Latency**: Irrelevant questions (e.g., *"Can any candidate pilot a commercial airplane?"*) cost \$0 and return in <50ms without touching the Groq API.

### 3. Sliding Context Window & Prompt Engineering
- **Model**: `openai/gpt-oss-120b` via Groq Cloud (131,072 token context window, leaving >125k token headroom with typical resume chunks).
- **Prompt Structure**:
  1. **System Prompt**: Recruiter Persona + Baked-in Graceful Decline Instruction + Optional Caution Clause.
  2. **Candidate Resume Context**: Labeled chunk blocks containing candidate filename and verbatim text.
  3. **Sliding Dialogue History**: The last $N=10$ messages (`session.messages.order_by("-created_at")[:10]`), chronologically reversed.
  4. **User Query**: The latest recruiter question.

### 4. Real-Time Token Streaming via SSE
- **Asynchronous Generator**: Consumes token deltas directly from `AsyncGroq` using:
  ```python
  stream = await client.chat.completions.create(
      model="openai/gpt-oss-120b",
      messages=messages,
      stream=True,
      temperature=0.2,
  )
  ```
- **Server-Sent Events (SSE)**: Relays token chunks through `StreamingHttpResponse(content_type="text/event-stream")`:
  ```text
  data: {"content": "Candidate "}
  data: {"content": "Jane Doe "}
  ...
  data: [DONE]
  ```

### 5. Resilient Turn Persistence
- Both the incoming user query and the full assistant response are persisted to `ChatMessage`.
- **Disconnect Guard**: The assistant message persistence runs in a `finally` block. If the client disconnects or aborts the connection mid-stream, whatever partial content was generated is safely saved so conversational dialogue turns remain paired in history.

---

## 🛠 Tech Stack

| Domain                  | Technology                                | Purpose                                               |
| Domain                  | Technology                                | Purpose                                               |
| :---------------------- | :---------------------------------------- | :---------------------------------------------------- |
| **Backend Framework**   | Django 6.1 + Django REST Framework        | Core API, ORM, multi-tenant business logic            |
| **Streaming Protocol**  | Server-Sent Events (SSE, EventSource)     | Real-time token streaming (`text/event-stream`)        |
| **Authentication**      | SimpleJWT + Argon2                        | Secure token management, hashing, Redis revocation    |
| **Task Queue & Async**  | Celery 5.6 + Redis                        | Distributed async processing, chord/group pipelines   |
| **Primary Database**    | PostgreSQL 16+ / Neon Serverless          | Relational storage with database branch isolation     |
| **Vector Search**       | `pgvector` (HNSW)                         | High-speed dense vector search on embeddings          |
| **Embeddings**          | `sentence-transformers/all-MiniLM-L6-v2`  | 384-dimensional CPU/GPU local dense embeddings        |
| **Document Processing** | PyMuPDF (`fitz`) + HuggingFace Tokenizers | PDF text extraction and token-sliding window chunking |
| **LLM Inference**       | Groq Cloud (`openai/gpt-oss-120b`)        | Structured entity extraction & conversational RAG     |
| **Async LLM Client**    | `AsyncGroq` + `Groq` SDK                  | Token-by-token streaming & parallel execution         |
| **Validation**          | Pydantic v2                               | Strict JSON schema parsing and response validation    |
| **Package Manager**     | `uv`                                      | Ultra-fast Python package and virtualenv manager      |
| **Testing**             | `pytest`, `pytest-django`, `factory-boy`  | Unit, integration, streaming, and chord testing       |

---

## 📁 Project Structure

```
resume_screener_django/
├── backend/
│   ├── accounts/                 # Company authentication & JWT management
│   │   ├── models.py             # Custom Company user model
│   │   ├── serializers.py        # Registration, token refresh serializers
│   │   ├── urls.py               # /api/auth/ endpoints
│   │   └── views.py              # Register, login, refresh, logout views
│   ├── config/                   # Django settings & Celery configuration
│   │   ├── settings/
│   │   │   ├── base.py           # Core settings, JWT, installed apps
│   │   │   ├── development.py    # Local debug, Redis cache, local DB
│   │   │   ├── production.py     # Strict SSL, HSTS, secure cookies
│   │   │   └── test.py           # Fast MD5 hashing, mock cache, test DB
│   │   ├── celery.py             # Celery app initialization
│   │   └── urls.py               # Main URL router
│   ├── jobs/                     # Screening, ranking, and RAG chat engine
│   │   ├── services/             # Pure business logic services
│   │   │   ├── chat.py           # Pre-filter, confidence routing, prompt builder, token streaming
│   │   │   ├── chunking.py       # Sliding-window token chunker
│   │   │   ├── embedding.py      # SentenceTransformer worker-cached embedder
│   │   │   ├── extraction.py     # PyMuPDF text parser
│   │   │   ├── extraction_llm.py # Groq structured skill extractor
│   │   │   ├── retrieval.py      # pgvector distance & top-2 aggregation
│   │   │   └── scoring.py        # Composite weighted scoring algorithm
│   │   ├── groq_client.py        # Groq and AsyncGroq client instances
│   │   ├── models.py             # Job, Resume, Application, ResumeChunk, ChatSession, ChatMessage
│   │   ├── serializers.py        # Job, Resume, Application, ChatSession, ChatMessage serializers
│   │   ├── tasks.py              # Celery tasks (process_resume, recompute, chord)
│   │   ├── urls.py               # Routes for jobs, resumes, applications, sessions, stream
│   │   └── views.py              # ViewSets and async chat_stream_view (SSE relay)
│   ├── scripts/
│   │   └── test_db.sh            # Ephemeral Neon DB branch tester
│   ├── tests/                    # Pytest test suite (31 unit & integration tests)
│   │   ├── factories.py          # FactoryBoy factories for all models
│   │   ├── test_chat_prefilter.py# Deterministic gate & confidence bands tests
│   │   ├── test_chat_prompt.py   # Sliding N=10 history & caution clause tests
│   │   ├── test_chat_sessions.py # Session CRUD, messages sub-endpoint, tenant isolation tests
│   │   ├── test_chat_stream.py   # AsyncGroq streaming, SSE relay & disconnect tests
│   │   ├── test_retrieval.py     # Tenant- and job-scoped retrieval tests
│   │   ├── test_scoring.py       # Composite scoring formula tests
│   │   └── test_*.py             # Remaining unit & pipeline tests
│   ├── conftest.py               # Pytest fixtures, mock Groq & embeddings
│   ├── manage.py
│   ├── pyproject.toml            # Project dependencies & tool configurations
│   └── uv.lock                   # Locked reproducible dependency tree
├── frontend/                     # Next.js frontend workspace
├── resume_screener.code-workspace
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- **uv** package manager ([Install uv](https://github.com/astral-sh/uv)):
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **PostgreSQL** with the [`pgvector`](https://github.com/pgvector/pgvector) extension enabled (or a [Neon](https://neon.tech) cloud database).
- **Redis** server running locally or via Docker:
  ```bash
  docker run -d -p 6379:6379 --name redis redis:7-alpine
  ```
- A **Groq API Key** ([Get free Groq API key](https://console.groq.com)).

---

### Environment Configuration

Create a `.env` file in the `backend/` directory:

```bash
cd backend
cp .env.example .env  # or create a new .env
```

Populate the required environment variables:

```ini
# Django Configuration
SECRET_KEY="your-super-secret-django-key"
DJANGO_SETTINGS_MODULE="config.settings.development"

# Database (PostgreSQL with pgvector enabled)
DATABASE_URL="postgresql://user:password@localhost:5432/resume_screener?sslmode=disable"

# Redis & Celery
REDIS_URL="redis://127.0.0.1:6379"
CELERY_BROKER_URL="redis://127.0.0.1:6379/0"
CELERY_RESULT_BACKEND="redis://127.0.0.1:6379/0"

# Groq API
GROQ_API_KEY="gsk_your_groq_api_key_here"

# Security (for production)
# ALLOWED_HOSTS="api.yourdomain.com"
```

---

### Installation with `uv`

Install all dependencies and create the virtual environment using `uv`:

```bash
cd backend
uv sync --all-groups
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

---

### Database Setup & Migrations

Ensure `pgvector` is available on your PostgreSQL database, then apply Django migrations:

```bash
# Enable pgvector extension (if not already enabled)
python manage.py shell -c "from django.db import connection; connection.cursor().execute('CREATE EXTENSION IF NOT EXISTS vector;')"

# Run migrations
python manage.py migrate
```

Create a superuser/company account:

```bash
python manage.py createsuperuser
```

---

### Running the Services

You need three terminal tabs or a process supervisor:

#### 1. Start Redis

```bash
redis-server
```

#### 2. Start Celery Worker

The worker preloads the `sentence-transformers/all-MiniLM-L6-v2` model into memory on startup:

```bash
cd backend
uv run celery -A config worker --loglevel=info -c 4
```

#### 3. Start Django Development Server

```bash
cd backend
uv run python manage.py runserver 0.0.0.0:8000
```

The API will now be available at `http://127.0.0.1:8000/`.

---

## 📡 API Reference

All requests outside of registration and login require the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

### Authentication

| Method | Endpoint              | Description                                        | Auth Required |
| :----- | :-------------------- | :------------------------------------------------- | :------------ |
| `POST` | `/api/auth/register/` | Register a new company account                     | No            |
| `POST` | `/api/auth/login/`    | Obtain JWT access and refresh token pair           | No            |
| `POST` | `/api/auth/refresh/`  | Refresh access token (validates against blocklist) | No            |
| `POST` | `/api/auth/logout/`   | Blacklist refresh token in Redis                   | Yes           |

#### Registration Request Example:

```json
POST /api/auth/register/
{
  "email": "recruiting@company.com",
  "company_name": "Acme Corporation",
  "password": "StrongPassword123!"
}
```

---

### Jobs API

| Method  | Endpoint                    | Description                                                  |
| :------ | :-------------------------- | :----------------------------------------------------------- |
| `GET`   | `/api/jobs/`                | List jobs owned by authenticated company                     |
| `POST`  | `/api/jobs/`                | Create a job posting (triggers embedding & skill extraction) |
| `GET`   | `/api/jobs/{id}/`           | Retrieve job details and ranking status                      |
| `PATCH` | `/api/jobs/{id}/`           | Update job details                                           |
| `POST`  | `/api/jobs/{id}/recompute/` | **Trigger AI candidate ranking pipeline**                    |

#### Create Job Posting:

```json
POST /api/jobs/
{
  "title": "Senior Backend Engineer (Python/Django)",
  "description": "We are looking for a Python specialist with at least 4 years of experience in Django, Celery, PostgreSQL, and distributed architectures.",
  "required_experience_years": 4,
  "head_count": 3
}
```

#### Trigger Candidate Ranking:

```http
POST /api/jobs/{id}/recompute/
```

**Response (`202 Accepted`):**

```json
{
  "detail": "Ranking recomputation started.",
  "ranking_status": "computing"
}
```

---

### Resumes API

| Method | Endpoint             | Description                                                |
| :----- | :------------------- | :--------------------------------------------------------- |
| `GET`  | `/api/resumes/`      | List resumes uploaded by company                           |
| `POST` | `/api/resumes/`      | Upload single or batch PDF resumes (`multipart/form-data`) |
| `GET`  | `/api/resumes/{id}/` | View resume parsing status and extracted skills            |

#### Upload Resumes (Multipart):

Send one or multiple files under the key `files` or `file`:

```bash
curl -X POST http://127.0.0.1:8000/api/resumes/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@john_doe_cv.pdf" \
  -F "files=@jane_smith_cv.pdf"
```

---

### Applications API

| Method | Endpoint                  | Description                                          |
| :----- | :------------------------ | :--------------------------------------------------- |
| `GET`  | `/api/applications/`      | List applications with nested job and resume details |
| `POST` | `/api/applications/`      | Associate a resume with a job posting                |
| `GET`  | `/api/applications/{id}/` | Inspect scores, rankings, and recruiter dossier      |

#### Application Result Representation:

```json
{
  "id": 42,
  "job": {
    "id": 1,
    "title": "Senior Backend Engineer (Python/Django)",
    "ranking_status": "done"
  },
  "resume": {
    "id": 105,
    "original_filename": "jane_smith_cv.pdf",
    "skills": ["python", "django", "postgresql", "docker", "redis"],
    "experience_years": 5
  },
  "retrieval_score": -0.842,
  "final_score": 88.75,
  "status": "SL",
  "llm_profile": {
    "summary": "Exceptional backend developer with direct experience in Django, asynchronous workflows with Celery, and database scaling.",
    "strengths": [
      "5 years of professional Python experience exceeding role requirements",
      "Demonstrated production work with Redis and Celery",
      "Strong vector alignment to system architecture needs"
    ],
    "gaps": ["No direct mention of Kubernetes or microservice orchestration"]
  },
  "created_at": "2026-09-05T21:30:00Z"
}
```

---

### Chat Sessions & Streaming API

| Method   | Endpoint                       | Description                                                                  |
| :------- | :----------------------------- | :--------------------------------------------------------------------------- |
| `GET`    | `/api/sessions/`               | List chat sessions for authenticated company (tenant-scoped)                 |
| `GET`    | `/api/sessions/?job={job_id}`  | Filter chat sessions for a specific job                                      |
| `POST`   | `/api/sessions/`               | Create a new chat session for a job (`{"job": <id>}`)                        |
| `GET`    | `/api/sessions/{id}/`          | Retrieve session details with nested message history                         |
| `GET`    | `/api/sessions/{id}/messages/` | Sub-endpoint to load chronologically ordered message history on session open |
| `POST`   | `/api/sessions/{id}/stream/`   | **Real-time SSE token stream (`text/event-stream`)** via AsyncGroq           |
| `DELETE` | `/api/sessions/{id}/`          | Delete chat session and its dialogue history                                 |

#### Create Chat Session:

```json
POST /api/sessions/
{
  "job": 1
}
```

**Response (`201 Created`):**

```json
{
  "id": 12,
  "job": 1,
  "job_title": "Senior Backend Engineer (Python/Django)",
  "company": 3,
  "messages": [],
  "created_at": "2026-09-12T15:30:00Z",
  "updated_at": "2026-09-12T15:30:00Z"
}
```

#### Stream Assistant Response (SSE):

Send a `POST` request with `Accept: text/event-stream`:

```bash
curl -N -X POST http://127.0.0.1:8000/api/sessions/12/stream/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"query": "Which candidates demonstrate experience with Celery and Redis?"}'
```

**Response Stream (`200 OK`, `Content-Type: text/event-stream`):**

```text
data: {"content": "Based on "}

data: {"content": "the resumes, Jane Smith "}

data: {"content": "demonstrates 5 years "}

data: {"content": "of hands-on Celery and Redis experience."}

data: [DONE]
```

*(If the query is out of scope or irrelevant, the pre-filter gate instantly yields a canned decline event without making an LLM call: `data: {"content": "I'm sorry, but I couldn't find any candidate information relevant to your question for this job posting."}` followed by `data: [DONE]`)*

---

## 🧪 Testing & Quality Assurance

The test suite contains **31 comprehensive automated tests** covering unit logic, vector normalization, composite scoring, Celery `chord` workflows, and the interactive RAG streaming chat assistant.

### Running Local Tests

```bash
cd backend
uv run pytest --reuse-db
```

### Running Specific Phase 6 Chat Tests

```bash
cd backend
uv run pytest tests/test_retrieval.py \
              tests/test_chat_prefilter.py \
              tests/test_chat_prompt.py \
              tests/test_chat_stream.py \
              tests/test_chat_sessions.py \
              --reuse-db
```

### Isolated Ephemeral Testing with Neon Branches

The project includes an automation script (`scripts/test_db.sh`) that provisions an instant, isolated Neon PostgreSQL branch per test run and deletes it upon completion:

```bash
cd backend
chmod +x scripts/test_db.sh
./scripts/test_db.sh
```

---

## 🗺 Roadmap

- [x] Multi-tenant company authentication & JWT revocation.
- [x] Asynchronous resume ingestion, chunking, and dense embedding.
- [x] pgvector HNSW integration with top-2 chunk aggregation.
- [x] Groq LLM-powered structured entity extraction (skills & experience).
- [x] Celery chord candidate ranking and automated recruiter dossier synthesis.
- [x] **Interactive Multi-Tenant RAG Chat Assistant**:
  - [x] Job-scoped candidate retrieval isolation.
  - [x] Three-tier deterministic confidence gate ($d \ge -0.20$ canned decline, $-0.35 \le d < -0.20$ caution prompt injection, $d < -0.35$ normal flow).
  - [x] Sliding $N=10$ chronologically ordered context window.
  - [x] Real-time token streaming via Server-Sent Events (`text/event-stream`) with `AsyncGroq`.
  - [x] Resilient dialogue persistence on stream completion and client disconnects.
  - [x] Session management CRUD and message history endpoints.
- [ ] Frontend dashboard built with Next.js & React (in `frontend/`).
- [ ] Direct ATS integrations (Greenhouse, Lever, Workday).
- [ ] Multi-format ingestion (DOCX, TXT, scanned image OCR via Docling).

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

