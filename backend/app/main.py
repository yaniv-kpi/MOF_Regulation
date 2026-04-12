import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .database import engine, get_db, setup_db_extensions
from .models import Base
from .schemas import CrawlStatusResponse, SearchResponse, StatsResponse
from .search import SearchService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----
    logger.info("Initialising database…")
    try:
        setup_db_extensions()
    except Exception as e:
        logger.warning(f"Extension setup warning (non-fatal): {e}")

    Base.metadata.create_all(bind=engine)

    # Create the tsvector update trigger
    _create_tsvector_trigger()

    logger.info("Database ready.")
    yield
    # ---- shutdown ----
    logger.info("Shutting down.")


app = FastAPI(
    title="Israeli Regulation Search",
    description=(
        "Full-text search engine for Israeli regulation documents sourced from gov.il"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@app.get("/api/search", response_model=SearchResponse, tags=["search"])
async def search(
    q: str = Query(..., min_length=1, max_length=500, description="Search query (Hebrew supported)"),
    page: int = Query(1, ge=1, le=200),
    limit: int = Query(10, ge=1, le=50),
    category: Optional[str] = Query(None),
):
    """
    Full-text search across all indexed regulation documents.
    Supports Hebrew and Latin text. Returns paginated results with snippets.
    """
    db = next(get_db())
    try:
        service = SearchService(db)
        return service.search(q, page=page, limit=limit, category=category)
    except Exception as e:
        logger.error(f"Search error for query '{q}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search service error")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Suggestions (autocomplete)
# ---------------------------------------------------------------------------


@app.get("/api/suggest", tags=["search"])
async def suggest(
    q: str = Query(..., min_length=1, max_length=200),
):
    """Return up to 8 title suggestions for autocomplete."""
    db = next(get_db())
    try:
        service = SearchService(db)
        return {"suggestions": service.get_suggestions(q)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


@app.get("/api/categories", tags=["metadata"])
async def get_categories():
    db = next(get_db())
    try:
        service = SearchService(db)
        return {"categories": service.get_categories()}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@app.get("/api/stats", tags=["metadata"])
async def get_stats():
    db = next(get_db())
    try:
        service = SearchService(db)
        return service.get_stats()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Crawl trigger
# ---------------------------------------------------------------------------


@app.post("/api/crawl", response_model=CrawlStatusResponse, tags=["admin"])
async def trigger_crawl(background_tasks: BackgroundTasks):
    """
    Start a background crawl of gov.il codex documents.
    The crawl runs asynchronously — check /api/stats to track progress.
    """
    from .crawler.govil_crawler import GovILCrawler

    async def _run():
        db = next(get_db())
        try:
            crawler = GovILCrawler(db)
            count = await crawler.crawl()
            logger.info(f"Background crawl complete: {count} documents saved.")
        except Exception as e:
            logger.error(f"Crawl failed: {e}", exc_info=True)
        finally:
            db.close()

    background_tasks.add_task(_run)
    return CrawlStatusResponse(
        status="started",
        message="Crawl started in background. Use GET /api/stats to monitor progress.",
    )


# ---------------------------------------------------------------------------
# Healthcheck
# ---------------------------------------------------------------------------


@app.get("/health", tags=["ops"])
async def health():
    db = next(get_db())
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    finally:
        db.close()
    return {"status": "ok", "database": db_status}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _create_tsvector_trigger() -> None:
    """
    Create a PostgreSQL trigger that auto-updates the search_vector column
    on every INSERT or UPDATE of a document row.
    Uses the 'simple' text search configuration — works for Hebrew Unicode text.
    """
    sql = """
    CREATE OR REPLACE FUNCTION documents_search_vector_update()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.search_vector :=
            setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
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
        logger.info("tsvector trigger created/updated.")
    except Exception as e:
        logger.warning(f"tsvector trigger setup warning: {e}")
