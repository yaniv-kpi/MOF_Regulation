"""
Seed script — downloads and indexes real documents from gov.il codex.

Run:  python -m app.seed

Downloads every confirmed document from
  https://www.gov.il/BlobFolder/guide/information-entities-codex/he/
extracts text (PDF via pypdf, DOCX via python-docx), and stores records
with the ORIGINAL gov.il URL so search results link directly to the source.
"""

import sys, os, asyncio, logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
from sqlalchemy import text as sqla_text

from app.database import engine, SessionLocal
from app.models import Base, Document
from app.crawler.govil_crawler import (
    _BASELINE_URLS,
    _stage2_enumerate,
    _title_from_url,
    _infer_category,
    _doc_type,
    _fname,
)
from app.crawler.text_extractor import extract_text_from_bytes, clean_text

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "he-IL,he;q=0.9",
}


async def _collect_urls() -> list[tuple[str, str, str]]:
    """
    Build the list of (url, title, category) to seed.
    Baseline list + URL enumeration (HEAD probes).
    """
    seen: dict[str, tuple[str, str, str]] = {
        url: (url, title, cat) for url, title, cat in _BASELINE_URLS
    }

    # Run HEAD-request enumeration to discover additional documents
    logger.info("Probing candidate URL patterns on gov.il…")
    enum = await _stage2_enumerate()
    added = 0
    for url, title, cat in enum:
        if url not in seen:
            seen[url] = (url, title, cat)
            added += 1
    logger.info(f"Enumeration added {added} new URLs (total: {len(seen)})")

    return list(seen.values())


async def seed_async() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    urls = await _collect_urls()
    logger.info(f"\nDownloading and indexing {len(urls)} documents from gov.il…\n")

    added = skipped = failed = 0

    async with httpx.AsyncClient(
        headers=_HEADERS,
        timeout=60,
        follow_redirects=True,
        verify=False,
    ) as client:
        for url, title, category in urls:
            # Skip if already indexed
            if db.query(Document).filter(Document.url == url).first():
                skipped += 1
                continue

            try:
                resp = await client.get(url)
                resp.raise_for_status()
                content = clean_text(extract_text_from_bytes(resp.content, url))

                if not content.strip():
                    logger.warning(f"  empty content — skipping {_fname(url)}")
                    failed += 1
                    continue

                db.add(Document(
                    url=url,
                    title=title,
                    content=content,
                    category=category,
                    document_type=_doc_type(url),
                    source_id=_fname(url),
                ))
                db.commit()
                words = len(content.split())
                logger.info(f"  ✓  {title}  ({words:,} words)")
                added += 1

            except Exception as e:
                logger.warning(f"  ✗  {_fname(url)}: {e}")
                failed += 1

            await asyncio.sleep(0.3)

    # Rebuild FTS search vectors
    try:
        db.execute(sqla_text("""
            UPDATE documents
            SET search_vector =
                setweight(to_tsvector('simple', COALESCE(title,   '')), 'A') ||
                setweight(to_tsvector('simple', COALESCE(content, '')), 'B')
            WHERE search_vector IS NULL
        """))
        db.commit()
    except Exception as e:
        logger.warning(f"Vector rebuild warning: {e}")

    db.close()
    print(f"\n{'─'*50}")
    print(f"  Added   : {added}")
    print(f"  Skipped : {skipped} (already in DB)")
    print(f"  Failed  : {failed}")
    print(f"{'─'*50}")
    print("  Seed complete — open http://localhost:3000 and search!")


def seed() -> None:
    asyncio.run(seed_async())


if __name__ == "__main__":
    seed()
