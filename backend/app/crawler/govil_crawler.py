"""
Crawler for https://www.gov.il/he/pages/information-entities-codex

The gov.il portal is protected by Reblaze WAF which blocks plain HTTP scrapers
(returns 403). We use Playwright (headless Chromium) to render the page like a
real browser, extract every document link from the rendered DOM, then download
and index each document.

Flow:
  1. Playwright renders CODEX_URL and extracts all BlobFolder / PDF / DOCX links.
  2. Fallback: if Playwright fails, a curated list of known URLs is used.
  3. Each document URL is downloaded via httpx (files are publicly accessible).
  4. Text is extracted from PDF / DOCX / HTML.
  5. Documents are upserted into PostgreSQL with the ORIGINAL gov.il URL as
     the link shown to users — so "Open document" always goes to gov.il directly.
"""

import asyncio
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..models import Document
from .text_extractor import extract_text_from_bytes, clean_text

logger = logging.getLogger(__name__)

CODEX_URL = "https://www.gov.il/he/pages/information-entities-codex"
BLOB_BASE = "https://www.gov.il/BlobFolder/guide/information-entities-codex/he/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8",
}

# ─── Curated fallback list ────────────────────────────────────────────────────
# Discovered by inspecting Google-indexed URLs from the codex BlobFolder.
# The crawler extends this list dynamically from the live page; this is the
# minimum baseline that always works even when Playwright isn't available.
KNOWN_URLS: list[tuple[str, str]] = [
    (f"{BLOB_BASE}Codex_codex1.pdf",
     "קודקס גופים מוסדרים — חלק 1"),
    (f"{BLOB_BASE}Codex_codex2.pdf",
     "קודקס גופים מוסדרים — חלק 2"),
    (f"{BLOB_BASE}Codex_Gate5_Part2_Chapter2-signA.pdf",
     "שער 5 חלק 2 פרק 2 — סימן א"),
    (f"{BLOB_BASE}Codex_Gate5_Part2_Chapter1-signC-version7.pdf",
     "שער 5 חלק 2 פרק 1 — סימן ג (גרסה 7)"),
    (f"{BLOB_BASE}Codex_Gate5_Part1_Chapter4.docx",
     "שער 5 חלק 1 פרק 4"),
    (f"{BLOB_BASE}regulation_2022-11-06_final_word.pdf",
     "תקנות — נובמבר 2022"),
]


class GovILCrawler:
    def __init__(self, db: Session):
        self.db = db
        self._seen: set[str] = set()

    # ─── Entry point ─────────────────────────────────────────────────────────

    async def crawl(self, max_docs: int = 500) -> int:
        """
        Crawl the gov.il codex page and index all regulation documents.
        Returns the number of documents saved/updated.
        """
        logger.info("Starting gov.il codex crawl…")

        # Step 1 — discover document URLs
        links = await self._discover_document_links()
        logger.info(f"Discovered {len(links)} document links")

        # Step 2 — download + index each document
        saved = 0
        async with httpx.AsyncClient(
            headers=HEADERS,
            timeout=60,
            follow_redirects=True,
            verify=False,
        ) as client:
            for url, title_hint in links[:max_docs]:
                if url in self._seen:
                    continue
                self._seen.add(url)
                try:
                    title, content, category, doc_type = await self._fetch_and_extract(
                        client, url, title_hint
                    )
                    if title or content:
                        self._upsert(url, title, content, category, doc_type)
                        saved += 1
                        if saved % 20 == 0:
                            logger.info(f"  …{saved} documents indexed")
                except Exception as e:
                    logger.warning(f"Skipping {url}: {e}")

                await asyncio.sleep(0.8)  # polite delay

        self._refresh_search_vectors()
        logger.info(f"Crawl complete — {saved} documents saved/updated.")
        return saved

    # ─── Discovery: Playwright + fallback ────────────────────────────────────

    async def _discover_document_links(self) -> list[tuple[str, str]]:
        """Return list of (url, title_hint). Tries Playwright first."""
        links = await self._playwright_extract()
        if not links:
            logger.warning("Playwright extraction returned nothing — using known URL list")
            links = list(KNOWN_URLS)
        # De-duplicate preserving order
        seen: set[str] = set()
        unique = []
        for url, title in links:
            if url not in seen:
                seen.add(url)
                unique.append((url, title))
        return unique

    async def _playwright_extract(self) -> list[tuple[str, str]]:
        """
        Render the gov.il codex page with headless Chromium and extract every
        link that points to a regulation document (PDF, DOCX, or BlobFolder path).
        """
        try:
            from playwright.async_api import async_playwright, TimeoutError as PWTimeout
        except ImportError:
            logger.warning("playwright not installed — skipping headless extraction")
            return []

        links: list[tuple[str, str]] = []
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(
                    user_agent=HEADERS["User-Agent"],
                    locale="he-IL",
                    extra_http_headers={"Accept-Language": "he-IL,he;q=0.9"},
                )
                page = await context.new_page()

                logger.info(f"Playwright: navigating to {CODEX_URL}")
                try:
                    await page.goto(CODEX_URL, wait_until="networkidle", timeout=45_000)
                except PWTimeout:
                    # Even on timeout we may have partial DOM — continue
                    logger.warning("Playwright: page load timed out, extracting partial DOM")

                # Extract every <a href> that looks like a document
                raw_links: list[dict] = await page.evaluate("""
                    () => {
                        const results = [];
                        document.querySelectorAll('a[href]').forEach(a => {
                            const href = a.href || '';
                            const text = (a.textContent || a.title || '').trim();
                            const lower = href.toLowerCase();
                            if (
                                lower.includes('blobfolder') ||
                                lower.endsWith('.pdf') ||
                                lower.endsWith('.docx') ||
                                lower.endsWith('.doc') ||
                                lower.includes('information-entities-codex')
                            ) {
                                results.push({ href, text });
                            }
                        });
                        return results;
                    }
                """)

                for item in raw_links:
                    href = item.get("href", "").strip()
                    text = item.get("text", "").strip()
                    if href and _is_document_url(href):
                        links.append((href, text or _title_from_url(href)))

                logger.info(f"Playwright: extracted {len(links)} document links")
                await browser.close()

        except Exception as e:
            logger.error(f"Playwright extraction failed: {e}")

        return links

    # ─── Download + text extraction ──────────────────────────────────────────

    async def _fetch_and_extract(
        self,
        client: httpx.AsyncClient,
        url: str,
        title_hint: str,
    ) -> tuple[str, str, str, str]:
        """Download `url` and return (title, content, category, doc_type)."""
        resp = await client.get(url)
        resp.raise_for_status()

        raw_text = extract_text_from_bytes(resp.content, url)

        title = title_hint or _title_from_url(url)
        category = _infer_category(url, raw_text)
        doc_type = "pdf" if url.lower().endswith(".pdf") else \
                   "docx" if url.lower().endswith((".docx", ".doc")) else "html"

        return clean_text(title), clean_text(raw_text), category, doc_type

    # ─── DB upsert ───────────────────────────────────────────────────────────

    def _upsert(
        self,
        url: str,
        title: str,
        content: str,
        category: str,
        doc_type: str,
    ) -> None:
        try:
            existing = self.db.query(Document).filter(Document.url == url).first()
            if existing:
                existing.title = title
                existing.content = content
                existing.category = category
                existing.document_type = doc_type
            else:
                self.db.add(Document(
                    url=url,
                    title=title,
                    content=content,
                    category=category,
                    document_type=doc_type,
                    source_id=_source_id_from_url(url),
                ))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"DB upsert failed for {url}: {e}")

    def _refresh_search_vectors(self) -> None:
        try:
            self.db.execute(text("""
                UPDATE documents
                SET search_vector =
                    setweight(to_tsvector('simple', COALESCE(title, '')), 'A') ||
                    setweight(to_tsvector('simple', COALESCE(content, '')), 'B')
                WHERE search_vector IS NULL
                   OR (updated_at IS NOT NULL AND updated_at > created_at)
            """))
            self.db.commit()
            logger.info("Search vectors refreshed.")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Vector refresh failed: {e}")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _is_document_url(url: str) -> bool:
    lower = url.lower()
    return (
        "blobfolder" in lower
        or lower.endswith(".pdf")
        or lower.endswith(".docx")
        or lower.endswith(".doc")
    ) and "gov.il" in url


def _title_from_url(url: str) -> str:
    """Generate a readable Hebrew-friendly title from a URL path."""
    path = urlparse(url).path.rstrip("/")
    filename = path.split("/")[-1]
    # Remove extension
    name = re.sub(r"\.(pdf|docx?|xlsx?)$", "", filename, flags=re.I)
    # Codex_Gate5_Part2_Chapter1-signC-version7 → readable label
    name = name.replace("_", " ").replace("-", " — ")
    return name.strip() or filename


def _infer_category(url: str, content: str) -> str:
    """Guess document category from filename or content keywords."""
    lower = url.lower()
    if "gate5" in lower or "שער5" in lower:
        return "שער 5 — ביטוח"
    if "gate4" in lower:
        return "שער 4"
    if "gate3" in lower:
        return "שער 3"
    if "gate2" in lower:
        return "שער 2"
    if "gate1" in lower:
        return "שער 1"
    if "regulation" in lower or "תקנות" in content[:200]:
        return "תקנות"
    if "codex" in lower:
        return "קודקס"
    return "גופים מוסדרים"


def _source_id_from_url(url: str) -> str:
    path = urlparse(url).path
    return path.split("/")[-1]
