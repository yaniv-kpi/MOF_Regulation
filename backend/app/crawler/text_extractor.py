"""
Utilities to extract clean plain text from HTML and PDF content.
Hebrew text is preserved as-is (Unicode). HTML tags and boilerplate are stripped.
"""

import re
import io
import logging
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_text_from_html(html: str, base_url: str = "") -> tuple[str, str]:
    """
    Parse HTML and return (title, body_text).
    Removes scripts, styles, nav, header, footer before extracting text.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove noise elements
    for tag in soup.find_all(
        ["script", "style", "nav", "header", "footer", "noscript", "iframe", "svg"]
    ):
        tag.decompose()

    # Try to find title
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()
    else:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    # Extract body text
    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(id="content")
        or soup.find(class_=re.compile(r"content|main|article", re.I))
        or soup.body
    )

    body_text = ""
    if main:
        body_text = main.get_text(separator=" ", strip=True)

    # Normalize whitespace
    body_text = re.sub(r"\s{2,}", " ", body_text).strip()

    return title, body_text


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract text from a PDF binary. Returns plain text.
    Uses pypdf (formerly PyPDF2). Falls back gracefully.
    """
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages_text.append(text)
        full_text = "\n".join(pages_text)
        return re.sub(r"\s{2,}", " ", full_text).strip()
    except ImportError:
        logger.warning("pypdf not installed — PDF text extraction skipped")
        return ""
    except Exception as e:
        logger.warning(f"PDF extraction error: {e}")
        return ""


def clean_text(text: str) -> str:
    """Normalize text: collapse whitespace, strip control characters."""
    # Remove null bytes and control chars (except newlines/tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Collapse multiple spaces / newlines
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
