from typing import Iterator

from document_processor.rag.rag_chain import (
    run_rag_chain,
    stream_rag_chain
)

from document_processor.rag.ingest import ingest_document

from document_processor.rag.logger import logger


def get_rag_response(query: str) -> dict:
    logger.info(f"[rag_service] Query: '{query}'")
    return run_rag_chain(query)


def stream_rag_response(query: str) -> Iterator[str]:
    logger.info(f"[rag_service] Streaming query: '{query}'")
    yield from _stream_rag_chain(query)


def ingest_file(file_path: str) -> dict:
    logger.info(f"[rag_service] Ingesting: {file_path}")
    chunks = ingest_document(file_path)
    return {
        "file":    file_path,
        "chunks":  chunks,
        "message": f"Successfully ingested {chunks} chunks.",
    }