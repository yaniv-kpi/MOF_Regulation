import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .database import engine, get_db, setup_db_extensions, _IS_SQLITE
from .models import Base
from .schemas import CrawlStatusResponse, SearchResponse
from .search import SearchService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting up — database: {'SQLite' if _IS_SQLITE else 'PostgreSQL'}")
    try:
        setup_db_extensions()
    except Exception as e:
        logger.warning(f"DB extensions (non-fatal): {e}")

    # Create tables (works for both SQLite and PostgreSQL)
    Base.metadata.create_all(bind=engine)

    # PostgreSQL-only: add search_vector column, GIN index, and trigger
    if not _IS_SQLITE:
        _setup_postgres_fts()

    logger.info("Database ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Israeli Regulation Search",
    description="Full-text search engine for Israeli regulation documents from gov.il",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# allow_credentials MUST be False when allow_origins=["*"].
# The frontend does not send cookies so this is correct.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Search ────────────────────────────────────────────────────────────────────

@app.get("/api/search", response_model=SearchResponse, tags=["search"])
async def search(
    q: str = Query(..., min_length=1, max_length=500),
    page: int = Query(1, ge=1, le=200),
    limit: int = Query(10, ge=1, le=50),
    category: Optional[str] = Query(None),
):
    db = next(get_db())
    try:
        return SearchService(db).search(q, page=page, limit=limit, category=category)
    except Exception as e:
        logger.error(f"Search error '{q}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search service error")
    finally:
        db.close()


@app.get("/api/suggest", tags=["search"])
async def suggest(q: str = Query(..., min_length=1, max_length=200)):
    db = next(get_db())
    try:
        return {"suggestions": SearchService(db).get_suggestions(q)}
    finally:
        db.close()


@app.get("/api/categories", tags=["metadata"])
async def get_categories():
    db = next(get_db())
    try:
        return {"categories": SearchService(db).get_categories()}
    finally:
        db.close()


@app.get("/api/stats", tags=["metadata"])
async def get_stats():
    db = next(get_db())
    try:
        return SearchService(db).get_stats()
    finally:
        db.close()


# ── Crawl trigger ─────────────────────────────────────────────────────────────

@app.post("/api/crawl", response_model=CrawlStatusResponse, tags=["admin"])
async def trigger_crawl(background_tasks: BackgroundTasks):
    from .crawler.govil_crawler import GovILCrawler

    async def _run():
        db = next(get_db())
        try:
            count = await GovILCrawler(db).crawl()
            logger.info(f"Crawl complete: {count} documents saved.")
        except Exception as e:
            logger.error(f"Crawl failed: {e}", exc_info=True)
        finally:
            db.close()

    background_tasks.add_task(_run)
    return CrawlStatusResponse(
        status="started",
        message="Crawl running in background — check GET /api/stats for progress.",
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health():
    db = next(get_db())
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        db.close()
    return {
        "status": "ok",
        "database": "ok" if db_ok else "error",
        "db_type": "sqlite" if _IS_SQLITE else "postgresql",
    }


# ── PostgreSQL FTS setup ──────────────────────────────────────────────────────

def _setup_postgres_fts() -> None:
    """
    Add search_vector TSVECTOR column (if missing), a GIN index, and a trigger
    that keeps it up to date. Safe to run on every startup (all statements are
    idempotent).
    """
    sql = """
    ALTER TABLE documents ADD COLUMN IF NOT EXISTS
        search_vector TSVECTOR;

    CREATE INDEX IF NOT EXISTS idx_documents_search_vector
        ON documents USING GIN(search_vector);

    CREATE INDEX IF NOT EXISTS idx_documents_title_trgm
        ON documents USING GIN(title gin_trgm_ops);

    CREATE OR REPLACE FUNCTION documents_search_vector_update()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.search_vector :=
            setweight(to_tsvector('simple', coalesce(NEW.title,   '')), 'A') ||
            setweight(to_tsvector('simple', coalesce(NEW.content, '')), 'B');
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS documents_search_vector_trigger ON documents;

    CREATE TRIGGER documents_search_vector_trigger
        BEFORE INSERT OR UPDATE ON documents
        FOR EACH ROW EXECUTE FUNCTION documents_search_vector_update();
    """
    try:
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        logger.info("PostgreSQL FTS column / index / trigger ready.")
    except Exception as e:
        logger.warning(f"PostgreSQL FTS setup warning (non-fatal): {e}")
