import time
import re
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from .models import Document
from .schemas import SearchResponse, DocumentResult

logger = logging.getLogger(__name__)


def _build_tsquery(query: str) -> str:
    """
    Convert free text to a PostgreSQL tsquery string.
    Handles Hebrew and Latin characters.
    Words are joined with & (AND).
    Falls back to | (OR) if AND yields no results (handled at call site).
    """
    # Remove characters that break tsquery syntax
    clean = re.sub(r"[\"'();:!?<>]", " ", query.strip())
    words = [w.strip() for w in clean.split() if len(w.strip()) >= 2]
    if not words:
        return ""
    # Wrap each word in a prefix match using :* so partial words still match
    return " & ".join(f"{w}:*" for w in words)


def _extract_snippet(content: str, query: str, max_length: int = 300) -> str:
    """
    Extract a relevant snippet from content around the first keyword match.
    Falls back to the start of the content if no match found.
    """
    if not content:
        return ""

    words = [w for w in query.split() if len(w) >= 2]
    best_pos = len(content)

    for word in words:
        pos = content.lower().find(word.lower())
        if 0 <= pos < best_pos:
            best_pos = pos

    if best_pos == len(content):
        # No keyword found — return start of content
        snippet = content[:max_length]
    else:
        start = max(0, best_pos - 80)
        end = min(len(content), start + max_length)
        snippet = ("..." if start > 0 else "") + content[start:end] + (
            "..." if end < len(content) else ""
        )

    return snippet.strip()


class SearchService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Main search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        page: int = 1,
        limit: int = 10,
        category: Optional[str] = None,
    ) -> SearchResponse:
        start_time = time.perf_counter()
        offset = (page - 1) * limit

        tsquery = _build_tsquery(query)

        # Try FTS first (AND semantics)
        results, total = self._fts_search(tsquery, query, offset, limit, category)

        # If FTS yields nothing, fall back to OR semantics
        if total == 0 and tsquery:
            or_tsquery = tsquery.replace(" & ", " | ")
            results, total = self._fts_search(
                or_tsquery, query, offset, limit, category
            )

        # If still nothing, fall back to ILIKE (handles very short queries, noise)
        if total == 0:
            results, total = self._ilike_search(query, offset, limit, category)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        doc_results = [
            DocumentResult(
                id=r["id"],
                title=r["title"],
                url=r["url"],
                snippet=r["snippet"],
                category=r.get("category") or "",
                document_type=r.get("document_type") or "",
                published_date=r.get("published_date") or "",
                rank=float(r.get("rank") or 0),
            )
            for r in results
        ]

        return SearchResponse(
            query=query,
            total=total,
            page=page,
            limit=limit,
            has_more=(offset + limit) < total,
            results=doc_results,
            search_time_ms=round(elapsed_ms, 2),
        )

    # ------------------------------------------------------------------
    # FTS search via tsvector
    # ------------------------------------------------------------------

    def _fts_search(
        self,
        tsquery_str: str,
        raw_query: str,
        offset: int,
        limit: int,
        category: Optional[str],
    ):
        if not tsquery_str:
            return [], 0

        category_filter = "AND category = :category" if category else ""

        sql = text(
            f"""
            SELECT
                id, title, url, category, document_type, published_date,
                ts_headline(
                    'simple',
                    COALESCE(content, ''),
                    to_tsquery('simple', :tsquery),
                    'MaxWords=40, MinWords=20, StartSel=<mark>, StopSel=</mark>'
                ) AS snippet,
                ts_rank_cd(search_vector, to_tsquery('simple', :tsquery), 32) AS rank
            FROM documents
            WHERE search_vector @@ to_tsquery('simple', :tsquery)
            {category_filter}
            ORDER BY rank DESC, id
            LIMIT :limit OFFSET :offset
            """
        )

        count_sql = text(
            f"""
            SELECT COUNT(*) FROM documents
            WHERE search_vector @@ to_tsquery('simple', :tsquery)
            {category_filter}
            """
        )

        params: dict = {"tsquery": tsquery_str, "limit": limit, "offset": offset}
        count_params: dict = {"tsquery": tsquery_str}
        if category:
            params["category"] = category
            count_params["category"] = category

        try:
            rows = self.db.execute(sql, params).mappings().all()
            total = self.db.execute(count_sql, count_params).scalar() or 0
            results = []
            for r in rows:
                snippet = r["snippet"] or _extract_snippet(
                    "", raw_query
                )
                results.append(dict(r))
                results[-1]["snippet"] = snippet
            return results, int(total)
        except Exception as e:
            logger.warning(f"FTS search failed: {e}")
            return [], 0

    # ------------------------------------------------------------------
    # Fallback ILIKE search
    # ------------------------------------------------------------------

    def _ilike_search(
        self,
        query: str,
        offset: int,
        limit: int,
        category: Optional[str],
    ):
        category_filter = "AND category = :category" if category else ""
        like_pattern = f"%{query}%"

        sql = text(
            f"""
            SELECT id, title, url, category, document_type, published_date,
                   content, 0.0 AS rank
            FROM documents
            WHERE (title ILIKE :pattern OR content ILIKE :pattern)
            {category_filter}
            ORDER BY
                CASE WHEN title ILIKE :pattern THEN 0 ELSE 1 END,
                id
            LIMIT :limit OFFSET :offset
            """
        )
        count_sql = text(
            f"""
            SELECT COUNT(*) FROM documents
            WHERE (title ILIKE :pattern OR content ILIKE :pattern)
            {category_filter}
            """
        )
        params: dict = {"pattern": like_pattern, "limit": limit, "offset": offset}
        count_params: dict = {"pattern": like_pattern}
        if category:
            params["category"] = category
            count_params["category"] = category

        try:
            rows = self.db.execute(sql, params).mappings().all()
            total = self.db.execute(count_sql, count_params).scalar() or 0
            results = []
            for r in rows:
                snippet = _extract_snippet(r.get("content") or "", query)
                entry = dict(r)
                entry["snippet"] = snippet
                results.append(entry)
            return results, int(total)
        except Exception as e:
            logger.error(f"ILIKE search failed: {e}")
            return [], 0

    # ------------------------------------------------------------------
    # Autocomplete suggestions
    # ------------------------------------------------------------------

    def get_suggestions(self, query: str, limit: int = 8) -> List[str]:
        """Return title suggestions using trigram similarity."""
        sql = text(
            """
            SELECT DISTINCT title
            FROM documents
            WHERE title ILIKE :pattern
            ORDER BY similarity(title, :query) DESC
            LIMIT :limit
            """
        )
        try:
            rows = self.db.execute(
                sql,
                {"pattern": f"%{query}%", "query": query, "limit": limit},
            ).all()
            return [r[0] for r in rows]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Stats & categories
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        try:
            total = self.db.execute(
                text("SELECT COUNT(*) FROM documents")
            ).scalar() or 0
            cats = self.db.execute(
                text(
                    """
                    SELECT category, COUNT(*) AS cnt
                    FROM documents
                    WHERE category IS NOT NULL AND category != ''
                    GROUP BY category
                    ORDER BY cnt DESC
                    LIMIT 20
                    """
                )
            ).mappings().all()
            last = self.db.execute(
                text("SELECT MAX(created_at) FROM documents")
            ).scalar()
            return {
                "total_documents": int(total),
                "categories": [dict(c) for c in cats],
                "last_crawled": str(last) if last else None,
            }
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {"total_documents": 0, "categories": [], "last_crawled": None}

    def get_categories(self) -> List[str]:
        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT DISTINCT category FROM documents
                    WHERE category IS NOT NULL AND category != ''
                    ORDER BY category
                    """
                )
            ).all()
            return [r[0] for r in rows]
        except Exception:
            return []
