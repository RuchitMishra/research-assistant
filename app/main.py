from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.routes import router

app = FastAPI(
    title="Multi-Step Research Assistant API",
    description="Agentic RAG over a document knowledge base with web fallback.",
    version="0.3.0",
)
app.include_router(router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
