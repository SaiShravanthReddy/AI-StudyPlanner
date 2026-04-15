"""RAG service: chunk syllabus text, build a FAISS vector index, retrieve relevant context per topic."""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 400
_CHUNK_OVERLAP = 80
_TOP_K = 3


class RAGService:
    """Builds an in-memory FAISS vector index from syllabus text and retrieves relevant chunks per topic.

    Uses LangChain's OpenAIEmbeddings for encoding and RecursiveCharacterTextSplitter for chunking.
    Falls back to no-op (returns empty lists) when OpenAI API key or LangChain packages are unavailable.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._embeddings: Any = None
        if settings.openai_api_key:
            try:
                from langchain_openai import OpenAIEmbeddings  # noqa: PLC0415

                self._embeddings = OpenAIEmbeddings(
                    api_key=settings.openai_api_key,
                    model="text-embedding-3-small",
                )
            except Exception:
                logger.warning("OpenAIEmbeddings unavailable; RAG enrichment disabled.")

    def build_index(self, syllabus_text: str) -> Any | None:
        """Chunk *syllabus_text* and build an in-memory FAISS index.

        Returns the FAISS vectorstore instance, or ``None`` when embeddings are
        unavailable or index creation fails.
        """
        if not self._embeddings:
            return None
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter  # noqa: PLC0415
            from langchain_community.vectorstores import FAISS  # noqa: PLC0415
        except ImportError:
            logger.warning("langchain-community not installed; skipping RAG index build.")
            return None

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=_CHUNK_SIZE,
            chunk_overlap=_CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks = splitter.split_text(syllabus_text)
        if not chunks:
            return None
        try:
            return FAISS.from_texts(chunks, self._embeddings)
        except Exception:
            logger.exception("Failed to build FAISS index from syllabus chunks.")
            return None

    def retrieve(self, index: Any, query: str, k: int = _TOP_K) -> list[str]:
        """Return the top-*k* most relevant syllabus chunks for *query*.

        Returns an empty list when *index* is ``None`` or retrieval fails.
        """
        if index is None:
            return []
        try:
            docs = index.similarity_search(query, k=k)
            return [doc.page_content for doc in docs]
        except Exception:
            logger.exception("RAG retrieval failed for query: %s", query)
            return []
