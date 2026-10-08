from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import get_settings


@lru_cache
def get_llm() -> ChatGoogleGenerativeAI:
    s = get_settings()
    return ChatGoogleGenerativeAI(
        model=s.llm_model,
        google_api_key=s.google_api_key,
        temperature=0,
        timeout=60,
        max_retries=3,
    )
