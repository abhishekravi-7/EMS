"""Retrieval: embed a question, search the vector store, select context.

Given a user question and a repository URL, returns the most relevant knowledge
chunks (already filtered to that repository) plus a concatenated context block
capped by a character budget so the prompt stays bounded.

Synchronous (embedding + Qdrant are sync); async callers use
``run_in_threadpool``. On-demand indexing when nothing is found is handled one
layer up (in the use case) to avoid an import cycle.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.exceptions import RagDisabledError
from app.infrastructure.rag import embedder, repo_index_locator, vector_store

logger = logging.getLogger(__name__)

# Upper bound on the assembled context so a large report can't blow the prompt.
# Reduced from 6000 to 4000 to speed up LLM prefill/processing time.
_CONTEXT_CHAR_BUDGET = 4000


@dataclass(frozen=True)
class RetrievalResult:
    context: str
    chunks: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.chunks


def retrieve(question: str, repository_url: str, job_id: str | None = None, top_k: int | None = None) -> RetrievalResult:
    """Return ranked knowledge chunks + a bounded context block for a repo.

    Raises :class:`RagDisabledError` when the retrieval stack is switched off.
    This is the single chokepoint every chat path funnels through, so guarding
    it here means the embedding model and vector store are never touched — the
    packages need not even be installed.
    """
    if not settings.rag_enabled:
        raise RagDisabledError()

    import re

    repository_url = repo_index_locator.normalize_repository_url(repository_url)
    limit = top_k or settings.rag_top_k

    # Embed question and search candidates
    embed_start = time.time()
    query_vector = embedder.embed_query(question)
    logger.debug("[Retriever] Query embedding completed in %.2fms", (time.time() - embed_start) * 1000)

    # Get more candidates for hybrid re-ranking
    search_start = time.time()
    search_limit = max(50, limit * 2)
    hits = vector_store.search(query_vector, repository_url, search_limit, job_id)
    logger.debug("[Retriever] Qdrant search completed in %.2fms", (time.time() - search_start) * 1000)

    # Keywords from question
    keywords = set(re.findall(r'[a-zA-Z0-9_\.\-]+', question.lower()))
    stopwords = {"what", "how", "why", "who", "which", "when", "where", "can", "java", "code", "file", "version", "project", "repo", "using", "uses", "use"}
    keywords = {kw for kw in keywords if len(kw) >= 3 and kw not in stopwords}

    # Rank candidates by hybrid scoring
    scored_hits = []
    for hit in hits:
        semantic_score = hit.get("_score", 0.0)
        keyword_score = 0.0

        text_lower = str(hit.get("text") or "").lower()
        file_path_lower = str(hit.get("file_path") or "").lower()
        class_name_lower = str(hit.get("class_name") or "").lower()
        method_name_lower = str(hit.get("method_name") or "").lower()

        for kw in keywords:
            if kw in file_path_lower:
                keyword_score += 0.5
            if kw in class_name_lower:
                keyword_score += 0.5
            if kw in method_name_lower:
                keyword_score += 0.3
            if kw in text_lower:
                keyword_score += 0.1

        version_pref = None
        if "before" in keywords or "original" in keywords:
            version_pref = "before"
        elif "after" in keywords or "migrated" in keywords or "upgrade" in keywords or "changed" in keywords:
            version_pref = "after"

        if version_pref and hit.get("version") == version_pref:
            keyword_score += 0.4

        combined_score = semantic_score + keyword_score
        scored_hits.append((combined_score, hit))

    scored_hits.sort(key=lambda x: x[0], reverse=True)
    hits = [item[1] for item in scored_hits]

    selected: list[dict[str, Any]] = []
    parts: list[str] = []
    used = 0
    for hit in hits:
        text = str(hit.get("text") or "").strip()
        if not text:
            continue
        chunk_type = str(hit.get("chunk_type") or "section")
        file_path = hit.get("file_path")
        version_str = f" ({hit.get('version')})" if hit.get("version") else ""
        file_header = f"File: {file_path}{version_str}\n" if file_path else ""

        block = f"[{chunk_type}]\n{file_header}{text}"
        if used + len(block) > _CONTEXT_CHAR_BUDGET and parts:
            break
        parts.append(block)
        selected.append(hit)
        used += len(block)

    return RetrievalResult(
        context="\n\n".join(parts),
        chunks=selected,
        metadata={
            "repository_url": repository_url,
            "limit": limit,
            "chunk_count": len(selected)
        }
    )
