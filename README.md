# Production Grade RAG Application

**Live demo:** https://graderagapp.streamlit.app (password protected, message me for access)

## Why I Built This

Most AI projects people build to learn RAG stop at the demo stage. You load a PDF, embed it, ask a question, get an answer, and call it done. That version works great on your laptop with one document and nobody hitting it at the same time. It falls apart the moment you actually try to run it for real users.

I wanted to understand what changes when you take a RAG pipeline from "it works on my machine" to something that could survive being deployed. What happens when OpenAI rate limits you mid request. What happens when two people upload documents at the same time. What happens when a step fails halfway through and you don't want to redo the whole pipeline from scratch. Those are the problems that actually show up in production, and they're the ones most tutorials skip entirely.

So I built this project specifically to learn how to solve them, then actually deployed it to real cloud infrastructure instead of stopping at a local demo. It's a PDF question answering system, but the interesting part isn't the RAG logic itself. It's the orchestration layer underneath it that makes the whole thing durable, observable, tested, containerized, and safe to run under real traffic.

## What It Solves

Any team building an internal document search tool, a customer support assistant, or a knowledge base chatbot runs into the same set of problems once they move past a prototype.

* API calls fail sometimes, and you need retries that don't duplicate work or lose progress
* Ingesting a document is slow, so it shouldn't block the user's request while it happens
* You need to prevent one user or one document from hammering your API and blowing your OpenAI bill
* When something breaks, you need to actually see where and why, not just get a stack trace in a terminal you already closed
* A public demo needs to be genuinely deployed and reachable, not just runnable on one developer's laptop

This project is my answer to those problems, built small enough to actually understand end to end but structured, tested, and deployed the way a real system would be.

## What It Does

You upload a PDF through a Streamlit interface. In the background, the document gets chunked, embedded using OpenAI's embedding model, and stored as vectors in a Qdrant database. Then you can ask questions about the document in plain English, and the app retrieves the most relevant chunks and uses GPT 4o mini to generate a grounded answer with the sources it pulled from.

The part that makes this different from a basic RAG demo is what's running underneath. Every step, ingesting a document and answering a question, runs as a durable function through Inngest. That means if a step fails or gets rate limited, it retries automatically without losing the work that already succeeded. Every run is traceable in a dashboard, so you can see exactly what happened, how long each step took, and where something broke if it does.

## Architecture

```
Streamlit UI  →  Inngest Event  →  Inngest Cloud  →  FastAPI Backend (Render)
                                                                    │
                                            ┌───────────────────────┼───────────────────────┐
                                            ▼                       ▼                       ▼
                                   Chunk & Embed PDF      Embed Query & Search      LLM Answer Generation
                                            │                       │                       │
                                            ▼                       ▼                       ▼
                                     Qdrant Cloud (upsert)   Qdrant Cloud (search)     OpenAI GPT 4o mini
```

The app is genuinely deployed across three managed services rather than only running locally:

* **Streamlit Community Cloud** hosts the frontend
* **Render** hosts the FastAPI backend and Inngest function handlers
* **Qdrant Cloud** hosts the vector database
* **Inngest Cloud** orchestrates events and durable function execution between the frontend and backend

Two functions drive the system.

**RAG: Ingest PDF** loads and chunks the uploaded document, embeds each chunk, and stores the vectors in Qdrant. It checks for already-embedded chunks using deterministic content-based IDs before calling the embeddings API, so re-uploading the same document doesn't re-embed content that's already stored. It's also configured with throttling and a per document rate limit, so the same file can't be re-ingested repeatedly and burn through API quota.

**RAG: Query PDF** embeds the user's question, searches Qdrant for the most relevant chunks, and calls the LLM to generate an answer grounded in that retrieved context.

Both functions are broken into small, independently retryable steps. That's the core idea behind Inngest, and it's what makes a multi stage AI pipeline survive things like an OpenAI 429 without having to restart the whole process from the beginning.

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration and durability | Inngest (Cloud) |
| Backend API | FastAPI, deployed on Render |
| Vector database | Qdrant Cloud |
| Embeddings and LLM | OpenAI (text embedding 3 large, GPT 4o mini) |
| Frontend | Streamlit, deployed on Streamlit Community Cloud |
| Containerization | Docker, Docker Compose |
| Testing | pytest, pytest-mock |
| Language | Python 3.11 |

## Security

The public demo sits behind a simple password gate on the Streamlit frontend, since every query triggers a real OpenAI API call that costs money. Without the correct password, the upload and question interface never renders.

## Testing

The project has a pytest suite covering chunking logic, the idempotent ingestion skip logic, and vector search formatting, all with OpenAI and Qdrant calls mocked so tests run without hitting real APIs or costing anything.

```bash
uv run pytest
```

## Retrieval Evaluation

A small evaluation script runs a set of test questions against the real ingested data and checks whether the correct source document is retrieved for each one. This project currently scores 100% (5/5) on its evaluation set, meaning every test question correctly surfaced its expected source document.

```bash
uv run python -m eval.run_eval
```

## Running Locally

You need three processes running at the same time.

```bash
# Inngest dev server, orchestrates events and function runs
npx inngest-cli@latest dev

# FastAPI backend, hosts the actual function code
uv run uvicorn main:app --reload

# Streamlit frontend
uv run streamlit run streamlit_app.py
```

Open `http://localhost:8501` to use the app, and `http://localhost:8288` to watch every run happen in real time, including retries and errors.

### Running Locally with Docker

The whole backend, frontend, and a local Qdrant instance can also run together with a single command:

```bash
docker compose up --build
```

You'll still need the Inngest dev server running separately alongside Docker (`npx inngest-cli@latest dev`), since it isn't containerized.

### Environment Variables

Create a `.env` file with:

```
OPENAI_API_KEY=your_key_here
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_key
INNGEST_EVENT_KEY=your_event_key
INNGEST_SIGNING_KEY=your_signing_key
INNGEST_ENV=production
BACKEND_URL=your_backend_url
```

## Project Structure

```
main.py            FastAPI app and Inngest function definitions
streamlit_app.py   Frontend, PDF upload and question answering interface
data_loader.py     PDF loading, chunking, and embedding helpers
vector_db.py       Qdrant client wrapper for upsert and similarity search
custom_types.py    Pydantic models for structured step outputs
tests/             pytest suite with mocked external dependencies
eval/              Retrieval accuracy evaluation script and test question set
Dockerfile         Container definition for the backend and frontend
docker-compose.yml Local multi-service orchestration (backend, frontend, Qdrant)
```

## What I Learned Building This

The biggest shift for me was realizing that reliability isn't something you bolt on later. It has to be part of how you structure the pipeline from the start. Breaking each stage into a discrete, retryable step changes how you write the code, not just how it behaves when something fails.

Deploying this to real infrastructure, rather than stopping at a working local demo, surfaced a whole category of problems that never show up locally: container-to-container networking, environment-specific service discovery, cold starts on free-tier hosting, and the difference between a local dev tool's convenience APIs and what a real hosted service actually exposes. Debugging those was a genuinely different skill than writing the RAG logic itself.

I also learned to think about cost and abuse prevention as part of the design, not an afterthought. Rate limiting by document source instead of globally meant one popular file couldn't starve out everyone else's requests, and gating the public demo behind a password meant a stranger finding the link couldn't run up my OpenAI bill.
