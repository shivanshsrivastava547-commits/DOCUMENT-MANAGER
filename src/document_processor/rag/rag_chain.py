# RAG chain logic
# backend/app/rag/rag_chain.py

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.documents import Document
from document_processor.rag.retriever import (
    retrieve_chunks,
    format_context
)

from document_processor.config.settings import settings
from document_processor.rag.logger import logger
from typing import Iterator


# ── LLM ───────────────────────────────────────────────────────────────────
llm = ChatGroq(
    model=settings.GROQ_MODEL,
    api_key=settings.GROQ_API_KEY,
    temperature=0.2,      # low temp → factual, grounded answers
)

# ── System prompt ──────────────────────────────────────────────────────────
RAG_SYSTEM_PROMPT = """You are a helpful assistant that answers questions
strictly based on the provided document context.

Rules:
- Only use information from the context below to answer.
- If the context does not contain enough information, say:
  "I couldn't find relevant information in the uploaded documents."
- Always mention which source/chunk supports your answer.
- Be concise and accurate. Do not make up information.
"""


# ── Standard invoke ────────────────────────────────────────────────────────
def run_rag_chain(query: str) -> dict:
    """
    Full RAG chain:
        1. Retrieve relevant chunks from FAISS
        2. Format chunks into a context block
        3. Call Groq LLaMA with system prompt + context + user query
        4. Return answer + source references

    Args:
        query : user's question

    Returns:
        dict with keys:
            - answer  : LLM answer string
            - sources : list of source file references
    """
    logger.info(f"[rag_chain] Running RAG for: '{query}'")

    # ── Step 1: Retrieve ───────────────────────────────────────────────────
    docs: list[Document] = retrieve_chunks(query)

    if not docs:
        logger.warning("[rag_chain] No chunks retrieved.")
        return {
            "answer":  "I couldn't find relevant information in the uploaded documents.",
            "sources": [],
        }

    # ── Step 2: Format context ─────────────────────────────────────────────
    context = format_context(docs)

    # ── Step 3: Build prompt + call LLM ───────────────────────────────────
    messages = [
        SystemMessage(content=RAG_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Context from documents:\n{context}\n\n"
            f"Question: {query}"
        )),
    ]

    try:
        response = llm.invoke(messages)
        answer: str = response.content
        logger.info("[rag_chain] LLM answered successfully.")
    except Exception as e:
        logger.error(f"[rag_chain] LLM error: {e}")
        raise

    # ── Step 4: Collect unique sources ────────────────────────────────────
    sources = list({
        doc.metadata.get("source", "Unknown") for doc in docs
    })

    return {
        "answer":  answer,
        "sources": sources,
    }


# ── Streaming invoke ───────────────────────────────────────────────────────
def stream_rag_chain(query: str) -> Iterator[str]:
    """
    Streaming version of run_rag_chain.
    Retrieves context first (blocking), then streams LLM tokens.
    Used by POST /api/rag/stream endpoint.
    """
    logger.info(f"[rag_chain] Streaming RAG for: '{query}'")

    docs: list[Document] = retrieve_chunks(query)

    if not docs:
        yield "I couldn't find relevant information in the uploaded documents."
        return

    context = format_context(docs)

    messages = [
        SystemMessage(content=RAG_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Context from documents:\n{context}\n\n"
            f"Question: {query}"
        )),
    ]

    try:
        for chunk in llm.stream(messages):
            if chunk.content:
                yield chunk.content
    except Exception as e:
        logger.error(f"[rag_chain] Stream error: {e}")
        raise