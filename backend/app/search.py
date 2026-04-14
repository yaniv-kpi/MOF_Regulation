import re
import time
import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from .models import Document
from .schemas import SearchResponse, DocumentResult
from .database import _IS_SQLITE

logger = logging.getLogger(__name__)


# ─── Snippet helpers ──────────────────────────────────────────────────────────

def _make_snippet(content: str, query: str, max_len: int = 300) -> str:
    """Extract a context window around the first keyword hit and wrap it in <mark>."""
    if not content:
        return ""
    words = [w for w in query.split() if len(w) >= 1]
    best_pos = len(content)
    for w in words:
        p = content.lower().find(w.lower())
        if 0 <= p < best_pos:
            best_pos = p

    if best_pos == len(content):
        raw = content[:max_len]
        prefix, suffix = "", ""
    else:
        start = max(0, best_pos - 80)
        end = min(len(content), start + max_len)
        raw = content[start:end]
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content) else ""

    # Highlight each word
    for w in words:
        escaped = re.escape(w)
        raw = re.sub(f"({escaped})", r"<mark class='highlight'>\1</mark>", raw, flags=re.I)

    return prefix + raw + suffix


def _build_tsquery(query: str) -> str:
    clean = re.sub(r'[\"\'();:!?<>]', " ", query.strip())
    words = [w.strip() for w in clean.split() if len(w.strip()) >= 2]
    if not words:
        return ""
    return " & ".join(f"{w}:*" for w in words)


# ─── Main service ─────────────────────────────────────────────────────────────

class SearchService:
    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        query: str,
        page: int = 1,
        limit: int = 10,
        category: Optional[str] = None,
    ) -> SearchResponse:
        start = time.perf_counter()
        offset = (page - 1) * limit

        if _IS_SQLITE:
            results, total = self._like_search(query, offset, limit, category)
        else:
            results, total = self._pg_fts_search(query, offset, limit, category)
            if total == 0:
                results, total = self._like_search(query, offset, limit, category)

        elapsed = (time.perf_counter() - start) * 1000

        doc_results = [
            DocumentResult(
                id=r["id"],
                title=r["title"],
                url=r["url"],
                snippet=r.get("snippet") or _make_snippet(r.get("content") or "", query),
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
            search_time_ms=round(elapsed, 2),
        )

    # ── PostgreSQL FTS ────────────────────────────────────────────────────────

    def _pg_fts_search(self, query: str, offset: int, limit: int, category: Optional[str]):
        tsq = _build_tsquery(query)
        if not tsq:
            return [], 0

        # First try AND semantics, then OR
        for operator_tsq in [tsq, tsq.replace(" & ", " | ")]:
            cat_filter = "AND category = :category" if category else ""
            try:
                sql = text(f"""
                    SELECT id, title, url, category, document_type, published_date,
                        ts_headline('simple', COALESCE(content,''),
                            to_tsquery('simple', :tsq),
                            'MaxWords=40,MinWords=20,StartSel=<mark class=''highlight''>,StopSel=</mark>'
                        ) AS snippet,
                        ts_rank_cd(search_vector, to_tsquery('simple', :tsq), 32) AS rank
                    FROM documents
                    WHERE search_vector @@ to_tsquery('simple', :tsq)
                    {cat_filter}
                    ORDER BY rank DESC
                    LIMIT :lim OFFSET :off
                """)
                count_sql = text(f"""
                    SELECT COUNT(*) FROM documents
                    WHERE search_vector @@ to_tsquery('simple', :tsq)
                    {cat_filter}
                """)
                params: dict = {"tsq": operator_tsq, "lim": limit, "off": offset}
                cp: dict = {"tsq": operator_tsq}
                if category:
                    params["category"] = category
                    cp["category"] = category

                rows = self.db.execute(sql, params).mappings().all()
                total = self.db.execute(count_sql, cp).scalar() or 0
                if total > 0:
                    return [dict(r) for r in rows], int(total)
            except Exception as e:
                logger.warning(f"PG FTS query failed: {e}")
                break  # fall through to LIKE

        return [], 0

    # ── LIKE search (works on both SQLite and PostgreSQL) ─────────────────────

    def _like_search(self, query: str, offset: int, limit: int, category: Optional[str]):
        words = [w.strip() for w in query.split() if w.strip()]
        if not words:
            return [], 0

        cat_filter = "AND category = :category" if category else ""

        # Build per-word conditions (all words must appear in title OR content)
        where_parts = []
        params: dict = {"lim": limit, "off": offset}
        for i, w in enumerate(words):
            params[f"w{i}"] = f"%{w}%"
            where_parts.append(f"(title LIKE :w{i} OR content LIKE :w{i})")
        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        if category:
            params["category"] = category

        # Title matches rank higher than content-only matches
        order_clause = (
            f"CASE WHEN title LIKE :w0 THEN 0 ELSE 1 END, id"
            if words else "id"
        )

        try:
            sql = text(f"""
                SELECT id, title, url, category, document_type, published_date, content,
                       0.0 AS rank
                FROM documents
                WHERE {where_clause} {cat_filter}
                ORDER BY {order_clause}
                LIMIT :lim OFFSET :off
            """)
            count_sql = text(f"""
                SELECT COUNT(*) FROM documents
                WHERE {where_clause} {cat_filter}
            """)

            rows = self.db.execute(sql, params).mappings().all()
            total = self.db.execute(count_sql, params).scalar() or 0

            results = []
            for r in rows:
                entry = dict(r)
                entry["snippet"] = _make_snippet(r.get("content") or "", query)
                results.append(entry)
            return results, int(total)

        except Exception as e:
            logger.error(f"LIKE search failed: {e}")
            return [], 0

    # ── Suggestions ───────────────────────────────────────────────────────────

    def get_suggestions(self, q: str, limit: int = 8) -> List[str]:
        try:
            rows = self.db.execute(
                text("SELECT DISTINCT title FROM documents WHERE title LIKE :p LIMIT :lim"),
                {"p": f"%{q}%", "lim": limit},
            ).all()
            return [r[0] for r in rows]
        except Exception:
            return []

    # ── Stats / categories ────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        try:
            total = self.db.execute(text("SELECT COUNT(*) FROM documents")).scalar() or 0
            cats = self.db.execute(text("""
                SELECT category, COUNT(*) AS cnt
                FROM documents
                WHERE category IS NOT NULL AND category != ''
                GROUP BY category ORDER BY cnt DESC LIMIT 20
            """)).mappings().all()
            last = self.db.execute(text("SELECT MAX(created_at) FROM documents")).scalar()
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
            rows = self.db.execute(text("""
                SELECT DISTINCT category FROM documents
                WHERE category IS NOT NULL AND category != ''
                ORDER BY category
            """)).all()
            return [r[0] for r in rows]
        except Exception:
            return []
