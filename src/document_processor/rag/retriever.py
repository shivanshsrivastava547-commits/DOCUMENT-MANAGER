# backend/app/rag/retriever.py

from pinecone import Pinecone
from langchain_core.documents import Document
from document_processor.config.settings import settings
from document_processor.rag.logger import logger

# ── Deep lazy singleton — loads on FIRST RAG call, not at startup ───────────
# Uses FastEmbed (ONNX-based) instead of sentence-transformers (torch-based).
# FastEmbed has NO torch/CUDA dependency — much lighter on Render free tier.
_embeddings = None

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_community.embeddings import FastEmbedEmbeddings  # deferred import
        logger.info("[retriever] Loading FastEmbed model (first request)...")
        _embeddings = FastEmbedEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
        )
        logger.info("[retriever] FastEmbed model loaded.")
    return _embeddings


def retrieve_chunks(query: str, k: int = None) -> list[Document]:
    """
    Embed the query and retrieve top-k most similar chunks from Pinecone.

    Returns list of LangChain Document objects.
    """
    k = k or settings.RAG_TOP_K
    logger.info(f"[retriever] Querying Pinecone for: '{query}' (top {k})")

    pc    = Pinecone(api_key=settings.PINECONE_API_KEY)
    index = pc.Index(settings.PINECONE_INDEX_NAME)

    query_vector = get_embeddings().embed_query(query)

    results = index.query(
        vector=query_vector,
        top_k=k,
        include_metadata=True,
    )

    docs = []
    for match in results.matches:
        meta = match.metadata or {}
        docs.append(Document(
            page_content=meta.get("text", ""),
            metadata={
                "source": meta.get("source", "Unknown"),
                "page":   meta.get("page", ""),
                "score":  match.score,
            },
        ))

    logger.info(f"[retriever] Retrieved {len(docs)} chunks.")
    return docs


def format_context(docs: list[Document]) -> str:
    """Format retrieved chunks into a numbered context block for the LLM prompt."""
    parts = []
    for i, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source", "Unknown")
        page   = doc.metadata.get("page", "")
        ref    = f"{source} p.{page}" if page else source
        score  = doc.metadata.get("score", 0)
        parts.append(
            f"[{i}] (Source: {ref} | Relevance: {score:.2f})\n{doc.page_content.strip()}"
        )
    return "\n\n".join(parts)
