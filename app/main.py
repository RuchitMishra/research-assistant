from fastapi import FastAPI
from fastapi.responses import RedirectResponse

app = FastAPI(
    title="Multi-Step Research Assistant API",
    description="Agentic RAG over a document knowledge base with web fallback.",
    version="0.1.0",
)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
