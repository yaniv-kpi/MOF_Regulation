"""
Crawler for https://www.gov.il/he/pages/information-entities-codex

gov.il uses Reblaze WAF, so plain httpx requests get 403 on the HTML page.
The actual document files (PDFs, DOCX) stored under BlobFolder are publicly
accessible and do NOT require authentication.

Three-stage discovery pipeline
────────────────────────────────
Stage 1 — Playwright
  Launch headless Chromium, render the JavaScript-heavy page, scrape every
  link whose href contains BlobFolder / .pdf / .docx.

Stage 2 — HEAD-request URL enumeration
  Systematically probe known filename patterns (Codex_GateN_PartN_ChapterN…)
  with concurrent HEAD requests. Files that return 200 are added to the list.

Stage 3 — Hardcoded baseline
  A curated list of URLs confirmed to exist, used as absolute minimum fallback.

After discovery each document is downloaded, text is extracted from PDF or
DOCX, and the record is upserted into PostgreSQL with the original gov.il URL
so every search result links directly back to the source document.
"""

import asyncio
import logging
import re
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..models import Document
from .text_extractor import extract_text_from_bytes, clean_text

logger = logging.getLogger(__name__)

CODEX_PAGE_URL = "https://www.gov.il/he/pages/information-entities-codex"
BLOB_BASE = "https://www.gov.il/BlobFolder/guide/information-entities-codex/he/"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
}

# ── Confirmed baseline documents (discovered from Google-indexed gov.il URLs) ──
_BASELINE_URLS: list[tuple[str, str, str]] = [
    (f"{BLOB_BASE}Codex_codex1.pdf",
     "קודקס גופים מוסדרים — חלק 1", "קודקס"),
    (f"{BLOB_BASE}Codex_codex2.pdf",
     "קודקס גופים מוסדרים — חלק 2", "קודקס"),
    (f"{BLOB_BASE}Codex_Gate5_Part2_Chapter2-signA.pdf",
     "שער 5 — חלק 2, פרק 2, סימן א", "שער 5"),
    (f"{BLOB_BASE}Codex_Gate5_Part2_Chapter1-signC-version7.pdf",
     "שער 5 — חלק 2, פרק 1, סימן ג (גרסה 7)", "שער 5"),
    (f"{BLOB_BASE}Codex_Gate5_Part1_Chapter4.docx",
     "שער 5 — חלק 1, פרק 4", "שער 5"),
    (f"{BLOB_BASE}regulation_2022-11-06_final_word.pdf",
     "תקנות — נובמבר 2022", "תקנות"),
]


# ─────────────────────────────────────────────────────────────────────────────
#  Main crawler class
# ─────────────────────────────────────────────────────────────────────────────

class GovILCrawler:
    def __init__(self, db: Session):
        self.db = db
        self._seen: set[str] = set()

    async def crawl(self, max_docs: int = 500) -> int:
        """
        Full crawl: discover → download → index.
        Returns number of documents saved/updated.
        """
        logger.info("=== gov.il codex crawl starting ===")

        links = await self._discover_all()
        logger.info(f"Total document links found: {len(links)}")

        saved = 0
        async with httpx.AsyncClient(
            headers=_BROWSER_HEADERS,
            timeout=60,
            follow_redirects=True,
            verify=False,
        ) as client:
            for url, title_hint, category in links[:max_docs]:
                if url in self._seen:
                    continue
                self._seen.add(url)
                try:
                    title, content, doc_type = await self._download_and_extract(
                        client, url, title_hint
                    )
                    if content.strip():
                        self._upsert(url, title, content, category, doc_type)
                        saved += 1
                        if saved % 10 == 0:
                            logger.info(f"  …{saved} documents indexed")
                except Exception as e:
                    logger.warning(f"  skip {_fname(url)}: {e}")
                await asyncio.sleep(0.5)

        self._rebuild_search_vectors()
        logger.info(f"=== Crawl complete: {saved} documents saved/updated ===")
        return saved

    # ── Discovery ─────────────────────────────────────────────────────────────

    async def _discover_all(self) -> list[tuple[str, str, str]]:
        """Run all three discovery stages, merge and de-duplicate."""
        results: dict[str, tuple[str, str, str]] = {}

        # Stage 1: Playwright
        playwright_links = await _stage1_playwright()
        for url, title, cat in playwright_links:
            results[url] = (url, title, cat)
        logger.info(f"Stage 1 (Playwright): {len(playwright_links)} links")

        # Stage 2: HEAD-request URL enumeration (runs concurrently)
        enum_links = await _stage2_enumerate()
        new_enum = 0
        for url, title, cat in enum_links:
            if url not in results:
                results[url] = (url, title, cat)
                new_enum += 1
        logger.info(f"Stage 2 (enumeration): {new_enum} additional links")

        # Stage 3: Baseline fallback
        for url, title, cat in _BASELINE_URLS:
            if url not in results:
                results[url] = (url, title, cat)

        return list(results.values())

    # ── Download + extract ────────────────────────────────────────────────────

    async def _download_and_extract(
        self,
        client: httpx.AsyncClient,
        url: str,
        title_hint: str,
    ) -> tuple[str, str, str]:
        """Download url, extract text, return (title, content, doc_type)."""
        resp = await client.get(url)
        resp.raise_for_status()

        content = clean_text(extract_text_from_bytes(resp.content, url))
        title = title_hint or _title_from_url(url)
        doc_type = _doc_type(url)
        return title, content, doc_type

    # ── DB ────────────────────────────────────────────────────────────────────

    def _upsert(
        self, url: str, title: str, content: str,
        category: str, doc_type: str,
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
                    url=url, title=title, content=content,
                    category=category, document_type=doc_type,
                    source_id=_fname(url),
                ))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"DB upsert failed ({_fname(url)}): {e}")

    def _rebuild_search_vectors(self) -> None:
        try:
            self.db.execute(text("""
                UPDATE documents
                SET search_vector =
                    setweight(to_tsvector('simple', COALESCE(title,   '')), 'A') ||
                    setweight(to_tsvector('simple', COALESCE(content, '')), 'B')
                WHERE search_vector IS NULL
                   OR updated_at > created_at
            """))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"search vector rebuild failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Stage 1 — Playwright
# ─────────────────────────────────────────────────────────────────────────────

async def _stage1_playwright() -> list[tuple[str, str, str]]:
    """
    Render the gov.il codex page with headless Chromium and extract every
    document link (PDF / DOCX under BlobFolder).
    """
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.warning("playwright not installed — skipping Stage 1")
        return []

    links: list[tuple[str, str, str]] = []
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            ctx = await browser.new_context(
                user_agent=_BROWSER_HEADERS["User-Agent"],
                locale="he-IL",
                extra_http_headers={"Accept-Language": "he-IL,he;q=0.9"},
            )
            page = await ctx.new_page()

            try:
                await page.goto(CODEX_PAGE_URL, wait_until="networkidle", timeout=60_000)
            except PWTimeout:
                logger.warning("Playwright: networkidle timeout — extracting partial DOM")

            raw: list[dict] = await page.evaluate("""
                () => {
                    const out = [];
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = (a.href || '').trim();
                        const text = (a.textContent || a.innerText || a.title || '').trim();
                        const lo = href.toLowerCase();
                        if (
                            href.includes('gov.il') && (
                                lo.includes('blobfolder') ||
                                lo.endsWith('.pdf') ||
                                lo.endsWith('.docx') ||
                                lo.endsWith('.doc')
                            )
                        ) {
                            out.push({ href, text });
                        }
                    });
                    return out;
                }
            """)

            await browser.close()

            for item in raw:
                url = item.get("href", "").strip()
                label = item.get("text", "").strip()
                if url and "gov.il" in url:
                    links.append((url, label or _title_from_url(url), _infer_category(url)))

    except Exception as e:
        logger.error(f"Playwright stage failed: {e}")

    return links


# ─────────────────────────────────────────────────────────────────────────────
#  Stage 2 — HEAD-request URL enumeration
# ─────────────────────────────────────────────────────────────────────────────

def _build_candidate_urls() -> list[str]:
    """
    Generate candidate document URLs based on observed naming conventions:
      Codex_GateG_PartP_ChapterC[.pdf|.docx]
      Codex_GateG_PartP_ChapterC-signS[.pdf]
      Codex_GateG_PartP_ChapterC-signS-versionV[.pdf]
      Codex_codexN.pdf
    """
    urls: list[str] = []

    # Simple numbered codex files
    for n in range(1, 20):
        urls.append(f"{BLOB_BASE}Codex_codex{n}.pdf")

    # Gate / Part / Chapter structure
    signs = ["A", "B", "C", "D", "E", "F"]
    for gate in range(1, 8):
        for part in range(1, 6):
            for chapter in range(1, 16):
                base = f"Codex_Gate{gate}_Part{part}_Chapter{chapter}"
                urls.append(f"{BLOB_BASE}{base}.pdf")
                urls.append(f"{BLOB_BASE}{base}.docx")
                for sign in signs:
                    urls.append(f"{BLOB_BASE}{base}-sign{sign}.pdf")
                    for ver in range(1, 12):
                        urls.append(f"{BLOB_BASE}{base}-sign{sign}-version{ver}.pdf")

    return urls


async def _stage2_enumerate(
    concurrency: int = 25,
) -> list[tuple[str, str, str]]:
    """
    Fire HEAD requests for every candidate URL concurrently.
    Only URLs that return HTTP 200 are kept.
    """
    candidates = _build_candidate_urls()
    logger.info(f"Stage 2: probing {len(candidates)} candidate URLs…")

    found: list[tuple[str, str, str]] = []
    sem = asyncio.Semaphore(concurrency)

    async def probe(client: httpx.AsyncClient, url: str) -> str | None:
        async with sem:
            try:
                resp = await client.head(url, timeout=10)
                if resp.status_code == 200:
                    return url
                # Some servers disallow HEAD — try GET with stream
                if resp.status_code == 405:
                    async with client.stream("GET", url, timeout=10) as r:
                        if r.status_code == 200:
                            return url
            except Exception:
                pass
            return None

    async with httpx.AsyncClient(
        headers=_BROWSER_HEADERS,
        follow_redirects=True,
        verify=False,
    ) as client:
        tasks = [probe(client, url) for url in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, str):
            found.append((result, _title_from_url(result), _infer_category(result)))

    logger.info(f"Stage 2: {len(found)} URLs confirmed")
    return found


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fname(url: str) -> str:
    return urlparse(url).path.split("/")[-1]


def _doc_type(url: str) -> str:
    lo = url.lower()
    if lo.endswith(".pdf"):
        return "pdf"
    if lo.endswith((".docx", ".doc")):
        return "docx"
    return "html"


def _title_from_url(url: str) -> str:
    """Convert a filename like Codex_Gate5_Part2_Chapter1-signC-version7.pdf
    into a human-readable Hebrew-friendly label."""
    name = _fname(url)
    name = re.sub(r"\.(pdf|docx?|xlsx?)$", "", name, flags=re.I)

    # Parse structured pattern
    m = re.match(
        r"Codex_Gate(\d+)_Part(\d+)_Chapter(\d+)"
        r"(?:-sign([A-Z]+))?(?:-version(\d+))?",
        name, re.I
    )
    if m:
        gate, part, chap, sign, ver = m.groups()
        label = f"שער {gate} — חלק {part}, פרק {chap}"
        if sign:
            label += f", סימן {sign}"
        if ver:
            label += f" (גרסה {ver})"
        return label

    m2 = re.match(r"Codex_codex(\d+)", name, re.I)
    if m2:
        return f"קודקס גופים מוסדרים — חלק {m2.group(1)}"

    # Generic fallback
    return name.replace("_", " ").replace("-", " — ").strip()


def _infer_category(url: str) -> str:
    lo = url.lower()
    for g in range(1, 8):
        if f"gate{g}" in lo:
            return f"שער {g}"
    if "regulation" in lo:
        return "תקנות"
    if "codex" in lo:
        return "קודקס"
    return "גופים מוסדרים"
