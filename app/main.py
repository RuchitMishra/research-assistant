from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.extra import router as extra_router
from app.api.routes import router

app = FastAPI(
    title="Multi-Step Research Assistant API",
    description="Agentic RAG over a document knowledge base with web fallback.",
    version="1.0.0",
)
app.include_router(router)
app.include_router(extra_router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


# Swagger UI shows `files` as array<string> ("Add string item") instead of a file picker for some
# FastAPI/Pydantic versions. Force the standard OpenAPI file-upload schema so /docs shows "Choose Files".
_original_openapi = app.openapi


def _openapi_with_file_upload_fix():
    schema = _original_openapi()
    for name, body in schema.get("components", {}).get("schemas", {}).items():
        if name.startswith("Body_upload_documents") and "files" in body.get("properties", {}):
            body["properties"]["files"] = {
                "type": "array", "title": "Files",
                "items": {"type": "string", "format": "binary"},
            }
    return schema


app.openapi = _openapi_with_file_upload_fix