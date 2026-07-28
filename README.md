# Production Grade RAG Application

## Why I Built This

Most AI projects people build to learn RAG stop at the demo stage. You load a PDF, embed it, ask a question, get an answer, and call it done. That version works great on your laptop with one document and nobody hitting it at the same time. It falls apart the moment you actually try to run it for real users.

I wanted to understand what changes when you take a RAG pipeline from "it works on my machine" to something that could survive being deployed. What happens when OpenAI rate limits you mid request. What happens when two people upload documents at the same time. What happens when a step fails halfway through and you don't want to redo the whole pipeline from scratch. Those are the problems that actually show up in production, and they're the ones most tutorials skip entirely.

So I built this project specifically to learn how to solve them. It's a PDF question answering system, but the interesting part isn't the RAG logic itself. It's the orchestration layer underneath it that makes the whole thing durable, observable, and safe to run under real traffic.

## What It Solves

Any team building an internal document search tool, a customer support assistant, or a knowledge base chatbot runs into the same set of problems once they move past a prototype.

* API calls fail sometimes, and you need retries that don't duplicate work or lose progress
* Ingesting a document is slow, so it shouldn't block the user's request while it happens
* You need to prevent one user or one document from hammering your API and blowing your OpenAI bill
* When something breaks, you need to actually see where and why, not just get a stack trace in a terminal you already closed

This project is my answer to those problems, built small enough to actually understand end to end but structured the way a real production system would be.

## What It Does

You upload a PDF through a simple Streamlit interface. In the background, the document gets chunked, embedded using OpenAI's embedding model, and stored as vectors in a Qdrant database. Then you can ask questions about the document in plain English, and the app retrieves the most relevant chunks and uses GPT 4o mini to generate a grounded answer with the sources it pulled from.

The part that makes this different from a basic RAG demo is what's running underneath. Every step, ingesting a document and answering a question, runs as a durable function through Inngest. That means if a step fails or gets rate limited, it retries automatically without losing the work that already succeeded. Every run is traceable in a dashboard, so you can see exactly what happened, how long each step took, and where something broke if it does.

## Architecture

```
Streamlit UI  →  Inngest Event  →  Inngest Dev Server  →  FastAPI Function Handler
                                                                    │
                                            ┌───────────────────────┼───────────────────────┐
                                            ▼                       ▼                       ▼
                                   Chunk & Embed PDF      Embed Query & Search      LLM Answer Generation
                                            │                       │                       │
                                            ▼                       ▼                       ▼
                                       Qdrant (upsert)        Qdrant (search)          OpenAI GPT 4o mini
```

Two functions drive the system.

**RAG: Ingest PDF** loads and chunks the uploaded document, embeds each chunk, and stores the vectors in Qdrant. It's configured with throttling and a per document rate limit, so the same file can't be re ingested over and over and burn through API quota.

**RAG: Query PDF** embeds the user's question, searches Qdrant for the most relevant chunks, and calls the LLM to generate an answer grounded in that retrieved context.

Both functions are broken into small, independently retryable steps. That's the core idea behind Inngest, and it's what makes a multi stage AI pipeline survive things like an OpenAI 429 without having to restart the whole process from the beginning.

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration and durability | Inngest |
| Backend API | FastAPI |
| Vector database | Qdrant |
| Embeddings and LLM | OpenAI (text embedding 3 large, GPT 4o mini) |
| Frontend | Streamlit |
| Language | Python 3.13 |

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

### Environment Variables

Create a `.env` file with:

```
OPENAI_API_KEY=your_key_here
```

## Project Structure

```
main.py            FastAPI app and Inngest function definitions
streamlit_app.py   Frontend, PDF upload and question answering interface
data_loader.py     PDF loading, chunking, and embedding helpers
vector_db.py       Qdrant client wrapper for upsert and similarity search
custom_types.py    Pydantic models for structured step outputs
```

## What I Learned Building This

The biggest shift for me was realizing that reliability isn't something you bolt on later. It has to be part of how you structure the pipeline from the start. Breaking each stage into a discrete, retryable step changes how you write the code, not just how it behaves when something fails.

I also learned to think about cost and abuse prevention as part of the design, not an afterthought. Rate limiting by document source instead of globally meant one popular file couldn't starve out everyone else's requests, and that's the kind of detail that only shows up once you think past "does it work" and into "does it work when other people are using it too."

---

*Inspired by Tech With Tim's Production Grade RAG walkthrough, extended and adapted independently.*
