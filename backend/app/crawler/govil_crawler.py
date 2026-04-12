"""
Crawler for https://www.gov.il/he/pages/information-entities-codex

Strategy:
1. First try gov.il's public JSON API endpoints (used by their own SPA).
2. Fall back to HTML scraping with BeautifulSoup.
3. For each document page, extract title + text content.
4. PDF links are downloaded and text is extracted.
5. All documents are upserted into the PostgreSQL `documents` table.
"""

import asyncio
import logging
import re
import json
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..models import Document
from .text_extractor import extract_text_from_html, extract_text_from_pdf, clean_text

logger = logging.getLogger(__name__)

GOVIL_BASE = "https://www.gov.il"
CODEX_URL = f"{GOVIL_BASE}/he/pages/information-entities-codex"

# Gov.il uses a REST API for their content management system.
# These endpoints return JSON lists of documents.
GOVIL_API_ENDPOINTS = [
    # The codex / open legislation pages
    f"{GOVIL_BASE}/he/api/pages/information-entities-codex",
    # Generic search/list endpoint (returns paginated JSON)
    f"{GOVIL_BASE}/he/api/GovExternalIntegration/govexternalintegration/GetGovEntitiesFilteredList",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class GovILCrawler:
    def __init__(self, db: Session):
        self.db = db
        self._seen_urls: set[str] = set()

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def crawl(self, max_docs: int = 5000) -> int:
        """
        Crawl gov.il codex page and all linked regulation documents.
        Returns the number of documents saved/updated.
        """
        logger.info("Starting gov.il codex crawl…")
        saved = 0

        async with httpx.AsyncClient(
            headers=HEADERS,
            timeout=30,
            follow_redirects=True,
            verify=False,  # Some gov.il certs can be problematic
        ) as client:
            # Step 1: discover document URLs
            doc_links = await self._discover_documents(client)
            logger.info(f"Discovered {len(doc_links)} document links")

            # Step 2: fetch + store each document
            for i, (url, meta) in enumerate(doc_links[:max_docs]):
                if url in self._seen_urls:
                    continue
                self._seen_urls.add(url)

                try:
                    title, content, category, doc_type, pub_date = (
                        await self._fetch_document(client, url, meta)
                    )
                    if title or content:
                        self._upsert_document(
                            url=url,
                            title=title or url,
                            content=content,
                            category=category or meta.get("category", ""),
                            document_type=doc_type or meta.get("type", "regulation"),
                            published_date=pub_date or meta.get("date", ""),
                            source_id=meta.get("source_id", ""),
                        )
                        saved += 1
                        if saved % 50 == 0:
                            logger.info(f"Saved {saved} documents so far…")
                except Exception as e:
                    logger.warning(f"Failed to process {url}: {e}")

                # Polite crawl delay
                await asyncio.sleep(1.0)

        # Refresh all search vectors after bulk insert
        self._refresh_search_vectors()
        logger.info(f"Crawl complete. Saved/updated {saved} documents.")
        return saved

    # ------------------------------------------------------------------
    # Discovery: find all document URLs on the codex page
    # ------------------------------------------------------------------

    async def _discover_documents(
        self, client: httpx.AsyncClient
    ) -> list[tuple[str, dict]]:
        """Returns list of (url, metadata_dict)."""
        links = []

        # --- Attempt 1: gov.il internal JSON API ---
        links += await self._discover_via_api(client)

        # --- Attempt 2: HTML scraping of the codex index page ---
        if len(links) < 10:
            links += await self._discover_via_html(client)

        # De-duplicate while preserving order
        seen = set()
        unique = []
        for item in links:
            if item[0] not in seen:
                seen.add(item[0])
                unique.append(item)

        return unique

    async def _discover_via_api(
        self, client: httpx.AsyncClient
    ) -> list[tuple[str, dict]]:
        """Try gov.il JSON API endpoints."""
        links: list[tuple[str, dict]] = []
        try:
            # The gov.il website exposes a JSON feed when called with the
            # right Accept header
            resp = await client.get(
                CODEX_URL,
                headers={**HEADERS, "Accept": "application/json"},
            )
            if resp.status_code == 200 and "application/json" in resp.headers.get(
                "content-type", ""
            ):
                data = resp.json()
                links += self._parse_api_response(data)
                logger.info(f"API returned {len(links)} links")
        except Exception as e:
            logger.debug(f"API discovery failed: {e}")

        # Also try the paginated list endpoint
        try:
            for page in range(1, 20):
                resp = await client.get(
                    f"{GOVIL_BASE}/he/api/datagovil/datasetlist",
                    params={"type": "codex", "page": page, "limit": 100},
                    headers=HEADERS,
                )
                if resp.status_code != 200:
                    break
                try:
                    data = resp.json()
                    batch = self._parse_api_response(data)
                    if not batch:
                        break
                    links += batch
                except Exception:
                    break
        except Exception as e:
            logger.debug(f"Paginated API failed: {e}")

        return links

    def _parse_api_response(self, data) -> list[tuple[str, dict]]:
        """Parse a gov.il JSON API response into (url, meta) pairs."""
        links = []
        items = []

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ("items", "data", "results", "documents", "entities"):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break

        for item in items:
            if not isinstance(item, dict):
                continue
            url = (
                item.get("url")
                or item.get("link")
                or item.get("pageUrl")
                or item.get("pageurl")
                or ""
            )
            if not url:
                continue
            if not url.startswith("http"):
                url = urljoin(GOVIL_BASE, url)

            meta = {
                "title": item.get("title") or item.get("name") or "",
                "category": item.get("category") or item.get("subject") or "",
                "date": item.get("date") or item.get("publishDate") or "",
                "source_id": str(item.get("id") or item.get("pageId") or ""),
                "type": "regulation",
            }
            links.append((url, meta))

        return links

    async def _discover_via_html(
        self, client: httpx.AsyncClient
    ) -> list[tuple[str, dict]]:
        """Scrape the codex HTML index page for document links."""
        links: list[tuple[str, dict]] = []
        try:
            resp = await client.get(CODEX_URL)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Remove nav/header noise
            for tag in soup.find_all(["nav", "header", "footer"]):
                tag.decompose()

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if not href or href.startswith("#") or href.startswith("javascript"):
                    continue

                # Normalize URL
                if href.startswith("/"):
                    href = urljoin(GOVIL_BASE, href)
                elif not href.startswith("http"):
                    continue

                # Only follow links back to gov.il
                if "gov.il" not in urlparse(href).netloc:
                    continue

                title = a_tag.get_text(strip=True) or ""
                meta = {
                    "title": title,
                    "category": "",
                    "date": "",
                    "source_id": "",
                    "type": "pdf" if href.lower().endswith(".pdf") else "regulation",
                }
                links.append((href, meta))

            logger.info(f"HTML scraping found {len(links)} links on codex page")

            # Also follow sub-pages linked from the codex index
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "/pages/" in href or "/codex/" in href:
                    sub_url = urljoin(GOVIL_BASE, href)
                    sub_links = await self._scrape_sub_index(client, sub_url)
                    links += sub_links

        except Exception as e:
            logger.warning(f"HTML discovery failed: {e}")

        return links

    async def _scrape_sub_index(
        self, client: httpx.AsyncClient, url: str
    ) -> list[tuple[str, dict]]:
        """Scrape a sub-index page for more document links."""
        links = []
        try:
            resp = await client.get(url, timeout=15)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "lxml")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if not href or href.startswith("#"):
                    continue
                full_url = urljoin(GOVIL_BASE, href)
                if "gov.il" not in urlparse(full_url).netloc:
                    continue
                meta = {
                    "title": a_tag.get_text(strip=True),
                    "category": "",
                    "date": "",
                    "source_id": "",
                    "type": "pdf" if href.lower().endswith(".pdf") else "regulation",
                }
                links.append((full_url, meta))
        except Exception as e:
            logger.debug(f"Sub-index scrape failed for {url}: {e}")
        return links

    # ------------------------------------------------------------------
    # Document fetch + content extraction
    # ------------------------------------------------------------------

    async def _fetch_document(
        self, client: httpx.AsyncClient, url: str, meta: dict
    ) -> tuple[str, str, str, str, str]:
        """
        Fetch a document URL and extract (title, content, category, doc_type, pub_date).
        Handles both HTML pages and PDF files.
        """
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "").lower()

        if "pdf" in content_type or url.lower().endswith(".pdf"):
            text_content = extract_text_from_pdf(resp.content)
            title = meta.get("title") or _infer_title_from_url(url)
            return (
                title,
                clean_text(text_content),
                meta.get("category", ""),
                "pdf",
                meta.get("date", ""),
            )

        # HTML document
        title, body = extract_text_from_html(resp.text, base_url=url)
        title = title or meta.get("title") or _infer_title_from_url(url)

        # Try to extract category / date from structured data or meta tags
        soup = BeautifulSoup(resp.text, "lxml")
        category = meta.get("category") or _extract_meta(soup, "category") or ""
        pub_date = meta.get("date") or _extract_meta(soup, "date") or _extract_meta(soup, "publishDate") or ""

        return (
            clean_text(title),
            clean_text(body),
            category,
            "regulation",
            pub_date,
        )

    # ------------------------------------------------------------------
    # Database upsert
    # ------------------------------------------------------------------

    def _upsert_document(
        self,
        url: str,
        title: str,
        content: str,
        category: str,
        document_type: str,
        published_date: str,
        source_id: str,
    ) -> None:
        """Insert a new document or update its content if URL already exists."""
        try:
            existing = (
                self.db.query(Document).filter(Document.url == url).first()
            )
            if existing:
                existing.title = title
                existing.content = content
                existing.category = category
                existing.document_type = document_type
                existing.published_date = published_date
            else:
                doc = Document(
                    url=url,
                    title=title,
                    content=content,
                    category=category,
                    document_type=document_type,
                    published_date=published_date,
                    source_id=source_id,
                )
                self.db.add(doc)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"DB upsert failed for {url}: {e}")

    def _refresh_search_vectors(self) -> None:
        """Rebuild the tsvector column for all documents after bulk load."""
        try:
            self.db.execute(
                text(
                    """
                    UPDATE documents
                    SET search_vector = to_tsvector(
                        'simple',
                        COALESCE(title, '') || ' ' || COALESCE(content, '')
                    )
                    WHERE search_vector IS NULL
                       OR (updated_at > created_at AND search_vector IS NOT NULL)
                    """
                )
            )
            self.db.commit()
            logger.info("Search vectors refreshed.")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Vector refresh failed: {e}")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _infer_title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    slug = path.split("/")[-1] if "/" in path else path
    return slug.replace("-", " ").replace("_", " ").title()


def _extract_meta(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"name": name}) or soup.find(
        "meta", attrs={"property": name}
    )
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""
