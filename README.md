# Multi-Step Research Assistant API

A FastAPI-based research assistant that answers questions using uploaded documents. It uses a knowledge base stored in Qdrant Cloud and can fall back to web search when the required information is not available in the documents.

## Live Demo

**API Docs:** https://research-assistant-3j2e.onrender.com/docs

**Health Check:** https://research-assistant-3j2e.onrender.com/health

> The application is deployed on Render's free tier, so the first request after a period of inactivity may take some time.

## Features

- Upload and process PDF, DOCX, HTML, TXT/MD and image files
- Store document embeddings in Qdrant Cloud
- Ask questions using the `/ask` endpoint
- Retrieve relevant information from the knowledge base
- Handle follow-up questions using session-based conversation history
- Detect ambiguous questions and ask for clarification
- Retry retrieval when the initial evidence is insufficient
- Use Tavily web search when the knowledge base cannot answer the question
- Return citations, web sources and the path taken by the agent

## Knowledge Base

- `summary-notes (2).pdf` — PDF
- `test.txt` — TXT
- `Logo_with_bg.png` — PNG
- `Autom8AI Intern Assignment.pdf` — PDF

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/documents` | Upload documents |
| GET | `/documents` | List uploaded documents |
| DELETE | `/documents/{doc_id}` | Delete a document |
| POST | `/ask` | Ask a question |
| GET | `/health` | Check API status |

## Example

Send a question to `/ask`:

```json
{
  "question": "What is AlphaGo?",
  "session_id": "test1"
}


## Architecture

The system follows a multi-step workflow:

```text
Question
   ↓
Plan
   ↓
Ambiguous? ── Yes ──→ Clarify
   ↓ No
Retrieve from Knowledge Base
   ↓
Grade Evidence
   ↓
Enough evidence?
   ├── Yes → Synthesize Answer
   └── No → Retry Retrieval
                  ↓
             Still insufficient?
                  ↓
              Web Search
                  ↓
             Synthesize Answer