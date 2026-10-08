# Multi-Step Research Assistant API

A FastAPI service that answers questions over a set of uploaded documents. Instead of one retrieve-then-generate call, the question goes through a small LangGraph workflow that plans the search, checks whether the retrieved text actually answers the question, and falls back to web search when it doesn't. Documents are embedded with Gemini and stored in Qdrant Cloud.

## Live demo

- API docs: https://research-assistant-3j2e.onrender.com/docs
- Chat page: https://research-assistant-3j2e.onrender.com/ui
- Health check: https://research-assistant-3j2e.onrender.com/health

It runs on Render's free tier, so after a period of inactivity the first request can take around a minute while the service wakes up.

## How it works

Every question to `/ask` goes through these steps:

Question
   ↓
Plan
   ↓
Ambiguous? ── Yes ──→ Clarify
   ↓ No
Retrieve from Knowledge Base
   ↓
Grade
   ↓
Enough evidence?
   ├── Yes → Synthesize Answer
   └── No → Retry Retrieval with better queries
                  ↓
             Still insufficient?
                  ↓
              Web Search
                  ↓
             Synthesize Answer


- **plan**: rewrites the question so it makes sense on its own (using the conversation history for follow-ups like "and what about the second one?"), splits compound questions into sub-questions, and decides whether the question is too vague to answer.
- **retrieve**: searches Qdrant once per sub-question and merges the results.
- **grade**: asks the model whether the retrieved text fully answers the question. If not, it also suggests better search queries for the retry.
- **web search**: Tavily, used only after the retry has also failed.
- **synthesize**: writes the answer using only the sources it was given, and reports which of them it actually used.

The response says where the answer came from (`knowledge_base`, `web`, `mixed`, `clarification_needed` or `not_found`), lists citations with file name, page and snippet, lists web sources separately, and includes a `reasoning_trace` with one line per step the graph took. Conversation memory uses the LangGraph checkpointer with `session_id` as the thread id.

## Why not plain RAG?

A plain pipeline retrieves once and answers from whatever came back. It has no way to notice that the retrieved text doesn't contain the answer. I added `/ask-naive`, which does exactly that (one retrieve, one generate), so the two can be compared. In the chat page, tick "Compare with naive RAG" to see both answers side by side.

Example question: *What is the boiling point of ethanol in Celsius?*

Naive RAG answered: "Based on the provided context, there is no mention of the boiling point of ethanol."

The multi-step version answered that it is about 78.37 degrees Celsius. The graded evidence from the documents was insufficient, so it retried, graded again, and then used web search.

```text
Naive:       retrieve -> generate
Multi-step:  plan -> retrieve -> grade -> retrieve (retry) -> grade -> web search -> synthesize
```

## Document ingestion

All file types go through the same `POST /documents` endpoint. The file is hashed (duplicates are skipped), loaded by a loader chosen from the file extension, split into chunks of about 1200 characters with 150 overlap, tagged with file name, page and chunk index, embedded and stored in Qdrant.

| Format | How it is read |
|---|---|
| PDF | Text layer via pypdf, with page numbers. If a PDF has no text (a scan), it is sent to Gemini for OCR |
| DOCX | docx2txt |
| HTML | BeautifulSoup, with scripts, styles and navigation removed |
| TXT / MD | Read as plain text |
| PNG / JPG / WEBP | OCR with Gemini vision |

The upload limit is 20 MB per file.

## Knowledge base

The current knowledge base is a small set I used to check that every ingestion path works:

- `summary-notes (2).pdf` (PDF)
- `Autom8AI_Intern_Assignment.pdf` (PDF)
- `test.txt` (plain text)
- `Logo_with_bg.png` (image, read with OCR)

The system itself doesn't depend on these. Uploading other files through `/documents` or the chat page adds them to the same collection.

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/documents` | Upload one or more documents |
| GET | `/documents` | List documents in the knowledge base |
| DELETE | `/documents/{doc_id}` | Delete a document and its chunks |
| POST | `/ask` | Ask a question through the multi-step graph |
| POST | `/ask-naive` | Single-pass baseline, for comparison |
| GET | `/health` | Check that the API is running |
| GET | `/ui` | Simple chat page |

Example request to `/ask`:

```json
{
  "question": "What is AlphaGo?",
  "session_id": "test1"
}
```

Use the same `session_id` for follow-up questions. A new `session_id` starts a fresh conversation.

## Evaluation
The project includes an evaluation set containing 10 questions across different categories:
- Simple questions
- Compound questions
- Follow-up questions
- Ambiguous questions
- Out-of-knowledge-base questions
The evaluation checks whether the system follows the expected path, such as:
Knowledge Base
Web Search
Mixed
Clarification Needed

Evaluation Result
10 / 10 test cases passed
The evaluation includes examples covering:
- Questions answered directly from the knowledge base
- Questions requiring information from multiple documents
- Follow-up questions using conversation history
- Ambiguous questions requiring clarification
- Questions requiring web search fallback
The evaluation can be run using:
python eval/run_eval.py

`eval/run_eval.py` sends the test questions in `eval/questions.json` to a running instance and writes a pass/fail table to `eval/results.md`:


## Running locally

```bash
git clone <repo-url>
cd research-assistant
python -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in the keys
uvicorn app.main:app --reload
```

The `.env` file needs these values (all have free tiers):

```text
GOOGLE_API_KEY=       # Google AI Studio
TAVILY_API_KEY=       # tavily.com
QDRANT_URL=           # Qdrant Cloud cluster URL, without :6333
QDRANT_API_KEY=
QDRANT_COLLECTION=kb
```

Then open http://localhost:8000/docs or http://localhost:8000/ui. There is also a Dockerfile; Render builds from it.

```bash
https://research-assistant-3j2e.onrender.com
```
