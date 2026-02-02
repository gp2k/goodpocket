"""
Content extraction service using trafilatura with readability-lxml fallback.
Extracts main content, title, and generates summary from web pages.
"""
import asyncio
from typing import TypedDict, Optional
from concurrent.futures import ThreadPoolExecutor

import httpx
import trafilatura
from readability import Document
from lxml import html
import structlog

from app.config import get_settings

logger = structlog.get_logger()

# Thread pool for CPU-bound extraction
_executor = ThreadPoolExecutor(max_workers=4)


class ExtractedContent(TypedDict):
    """Extracted content from a URL."""
    title: Optional[str]
    canonical_url: Optional[str]
    text: str
    summary: str


async def fetch_html(url: str) -> str:
    """
    Fetch HTML content from a URL with safety limits.
    
    Args:
        url: URL to fetch
        
    Returns:
        HTML content as string
        
    Raises:
        httpx.HTTPError: On network errors
        ValueError: If response is too large
    """
    settings = get_settings()
    
    async with httpx.AsyncClient(
        timeout=settings.fetch_timeout_seconds,
        follow_redirects=True,
        max_redirects=5,
    ) as client:
        response = await client.get(
            url,
            headers={
                "User-Agent": settings.fetch_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        response.raise_for_status()
        
        # Check content length
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > settings.fetch_max_size_bytes:
            raise ValueError(f"Response too large: {content_length} bytes")
        
        # Read with size limit
        content = response.text
        if len(content) > settings.fetch_max_size_bytes:
            raise ValueError(f"Response too large: {len(content)} bytes")
        
        return content


def _extract_with_trafilatura(html_content: str, url: str) -> Optional[ExtractedContent]:
    """
    Extract content using trafilatura (runs in thread pool).
    
    Args:
        html_content: Raw HTML
        url: Original URL for metadata extraction
        
    Returns:
        ExtractedContent or None if extraction fails
    """
    try:
        # Extract main content
        text = trafilatura.extract(
            html_content,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_precision=True,
            url=url,
        )
        
        if not text:
            return None
        
        # Extract metadata
        metadata = trafilatura.extract_metadata(html_content)
        
        title = metadata.title if metadata else None
        canonical = metadata.url if metadata else None
        
        # Generate summary (first 3 sentences or 500 chars)
        summary = _generate_summary(text)
        
        return ExtractedContent(
            title=title,
            canonical_url=canonical,
            text=text,
            summary=summary,
        )
        
    except Exception as e:
        logger.warning("Trafilatura extraction failed", error=str(e))
        return None


def _extract_with_readability(html_content: str) -> Optional[ExtractedContent]:
    """
    Fallback extraction using readability-lxml.
    
    Args:
        html_content: Raw HTML
        
    Returns:
        ExtractedContent or None if extraction fails
    """
    try:
        doc = Document(html_content)
        title = doc.title()
        
        # Get clean HTML content
        content_html = doc.summary()
        
        # Parse and extract text
        tree = html.fromstring(content_html)
        text = tree.text_content()
        
        # Clean up whitespace
        text = " ".join(text.split())
        
        if not text:
            return None
        
        summary = _generate_summary(text)
        
        return ExtractedContent(
            title=title,
            canonical_url=None,
            text=text,
            summary=summary,
        )
        
    except Exception as e:
        logger.warning("Readability extraction failed", error=str(e))
        return None


def _generate_summary(text: str, max_sentences: int = 3, max_chars: int = 500) -> str:
    """
    Generate a simple extractive summary.
    
    Args:
        text: Full text content
        max_sentences: Maximum number of sentences
        max_chars: Maximum character length
        
    Returns:
        Summary string
    """
    if not text:
        return ""
    
    # Split by sentence-ending punctuation
    sentences = []
    current = []
    
    for char in text:
        current.append(char)
        if char in ".!?。":
            sentence = "".join(current).strip()
            if len(sentence) > 10:  # Skip very short "sentences"
                sentences.append(sentence)
            current = []
    
    # Add remaining text if it looks like a sentence
    if current:
        remaining = "".join(current).strip()
        if len(remaining) > 10:
            sentences.append(remaining)
    
    # Take first N sentences up to max_chars
    summary_parts = []
    total_length = 0
    
    for sentence in sentences[:max_sentences]:
        if total_length + len(sentence) > max_chars:
            break
        summary_parts.append(sentence)
        total_length += len(sentence)
    
    summary = " ".join(summary_parts)
    
    # If still too long, truncate
    if len(summary) > max_chars:
        summary = summary[:max_chars - 3] + "..."
    
    return summary


async def extract_content(url: str) -> ExtractedContent:
    """
    Extract content from a URL.
    
    Uses trafilatura as primary extractor with readability-lxml fallback.
    
    Args:
        url: URL to extract content from
        
    Returns:
        ExtractedContent with title, text, and summary
        
    Raises:
        Exception: If all extraction methods fail
    """
    logger.info("Extracting content", url=url)
    
    # Fetch HTML
    html_content = await fetch_html(url)
    
    loop = asyncio.get_event_loop()
    
    # Try trafilatura first
    result = await loop.run_in_executor(
        _executor,
        _extract_with_trafilatura,
        html_content,
        url
    )
    
    if result:
        logger.info("Content extracted with trafilatura", url=url)
        return result
    
    # Fallback to readability
    result = await loop.run_in_executor(
        _executor,
        _extract_with_readability,
        html_content
    )
    
    if result:
        logger.info("Content extracted with readability fallback", url=url)
        return result
    
    # Return empty content if all methods fail
    logger.warning("All extraction methods failed", url=url)
    return ExtractedContent(
        title=None,
        canonical_url=None,
        text="",
        summary="",
    )
