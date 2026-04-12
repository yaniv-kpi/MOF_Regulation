"""
Seed script — downloads and indexes a curated set of real documents
directly from https://www.gov.il/BlobFolder/guide/information-entities-codex/he/

Run with:  python -m app.seed

This provides real, searchable data instantly without needing a full crawl.
All "Open document" links point directly to gov.il.
"""

import sys
import os
import asyncio
import logging

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import engine, SessionLocal
from app.models import Base, Document
from app.crawler.text_extractor import extract_text_from_bytes, clean_text
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BLOB_BASE = "https://www.gov.il/BlobFolder/guide/information-entities-codex/he/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "he-IL,he;q=0.9",
}

# Real documents from the gov.il codex BlobFolder.
# (url, title, category)
SEED_DOCUMENTS = [
    (
        f"{BLOB_BASE}Codex_codex1.pdf",
        "קודקס גופים מוסדרים — חלק 1",
        "קודקס",
    ),
    (
        f"{BLOB_BASE}Codex_codex2.pdf",
        "קודקס גופים מוסדרים — חלק 2",
        "קודקס",
    ),
    (
        f"{BLOB_BASE}Codex_Gate5_Part2_Chapter2-signA.pdf",
        "שער 5 — חלק 2, פרק 2, סימן א",
        "שער 5 — ביטוח",
    ),
    (
        f"{BLOB_BASE}Codex_Gate5_Part2_Chapter1-signC-version7.pdf",
        "שער 5 — חלק 2, פרק 1, סימן ג (גרסה 7)",
        "שער 5 — ביטוח",
    ),
    (
        f"{BLOB_BASE}Codex_Gate5_Part1_Chapter4.docx",
        "שער 5 — חלק 1, פרק 4",
        "שער 5 — ביטוח",
    ),
    (
        f"{BLOB_BASE}regulation_2022-11-06_final_word.pdf",
        "תקנות — נובמבר 2022",
        "תקנות",
    ),
]


async def _download_and_extract(url: str) -> str:
    """Download a document from gov.il and extract its text."""
    async with httpx.AsyncClient(
        headers=HEADERS,
        timeout=60,
        follow_redirects=True,
        verify=False,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text_content = extract_text_from_bytes(resp.content, url)
        return clean_text(text_content)


async def seed_async():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    added = 0
    skipped = 0
    failed = 0

    for url, title, category in SEED_DOCUMENTS:
        existing = db.query(Document).filter(Document.url == url).first()
        if existing:
            logger.info(f"  skip (exists): {title}")
            skipped += 1
            continue

        logger.info(f"  downloading: {url}")
        try:
            content = await _download_and_extract(url)
            doc_type = "pdf" if url.lower().endswith(".pdf") else "docx"
            doc = Document(
                url=url,
                title=title,
                content=content,
                category=category,
                document_type=doc_type,
                published_date="",
                source_id=url.split("/")[-1],
            )
            db.add(doc)
            db.commit()
            word_count = len(content.split()) if content else 0
            logger.info(f"  ✓ saved ({word_count} words): {title}")
            added += 1
        except Exception as e:
            logger.warning(f"  ✗ failed ({url}): {e}")
            failed += 1

    # Rebuild search vectors
    try:
        db.execute(text("""
            UPDATE documents
            SET search_vector =
                setweight(to_tsvector('simple', COALESCE(title, '')), 'A') ||
                setweight(to_tsvector('simple', COALESCE(content, '')), 'B')
            WHERE search_vector IS NULL
        """))
        db.commit()
    except Exception as e:
        logger.warning(f"Vector refresh warning: {e}")

    db.close()
    print(f"\n✅ Seed complete: {added} added, {skipped} already existed, {failed} failed.")
    if failed:
        print("   Failed documents may be temporarily unavailable on gov.il.")


def seed():
    asyncio.run(seed_async())


if __name__ == "__main__":
    seed()
