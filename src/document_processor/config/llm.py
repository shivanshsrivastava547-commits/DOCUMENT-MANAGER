
# LLM.py

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq


# Load the .env file located beside this Python file.
PROJECT_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(PROJECT_ROOT / ".env")

# Read project-specific configuration.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)


def get_document_llm() -> ChatGroq:
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is missing. Add it to Content_Planner/.env"
        )

    return ChatGroq(
        model=GROQ_MODEL,
        api_key=GROQ_API_KEY,
        temperature=0,
        reasoning_effort="low",
        max_tokens=2048,
    )


llm = get_document_llm()