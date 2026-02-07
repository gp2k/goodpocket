"""
Bookmark CRUD API endpoints.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
import structlog

from app.auth import get_current_user, CurrentUser
from app.models import (
    BookmarkCreate,
    BookmarkResponse,
    BookmarkListResponse,
    BookmarkDetail,
    MessageResponse,
)
from app.services.content_extractor import extract_content
from app.services.tag_generator import generate_tags
from app.services.ssrf_protection import validate_url
from app.utils.rate_limiter import check_rate_limit
from app import database as db

logger = structlog.get_logger()

router = APIRouter()


@router.post(
    "/bookmarks",
    response_model=BookmarkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a new bookmark",
    description="Fetches the URL, extracts content, generates tags, and saves the bookmark.",
)
async def create_bookmark(
    bookmark: BookmarkCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Create a new bookmark from a URL."""
    logger.info("Creating bookmark", user_id=str(user.id), url=str(bookmark.url))
    
    # Check rate limit
    await check_rate_limit(user.id, "saves")
    
    # Validate URL for SSRF
    url_str = str(bookmark.url)
    if not validate_url(url_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or blocked URL",
        )
    
    # Check for duplicate URL
    existing = await db.fetchrow(
        "SELECT id FROM bookmarks WHERE user_id = $1 AND url = $2",
        user.id, url_str
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bookmark already exists for this URL",
        )
    
    # Extract content from URL
    try:
        content = await extract_content(url_str)
    except Exception as e:
        logger.warning("Content extraction failed", url=url_str, error=str(e))
        content = {
            "title": bookmark.title,
            "canonical_url": None,
            "text": "",
            "summary": "",
        }
    
    # Use provided title or extracted title
    title = bookmark.title or content.get("title")
    
    # Generate tags from content
    tags = generate_tags(
        title=title or "",
        text=content.get("text", "")[:2000],
    )
    # #region agent log
    try:
        _log_path = __import__("pathlib").Path(__file__).resolve().parents[2] / ".cursor" / "debug.log"
        if _log_path.parent.exists():
            _text = content.get("text", "") or ""
            with open(_log_path, "a", encoding="utf-8") as _f:
                _f.write(__import__("json").dumps({"hypothesisId": "H2", "runId": "create_bookmark", "location": "bookmarks.py:create", "message": "generate_tags result at create", "data": {"tags_count": len(tags), "text_length": len(_text)}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
    except Exception:
        pass
    # #endregion

    # Insert bookmark
    row = await db.fetchrow(
        """
        INSERT INTO bookmarks (
            user_id, url, canonical_url, title, summary,
            extracted_text_excerpt, tags, status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending_embedding')
        RETURNING id, url, canonical_url, title, tags, status, cluster_id, cluster_label, created_at
        """,
        user.id,
        url_str,
        content.get("canonical_url"),
        title,
        content.get("summary"),
        content.get("text", "")[:2000],
        tags,
    )
    
    logger.info("Bookmark created", bookmark_id=str(row["id"]), tags=tags)
    
    return BookmarkResponse(
        id=row["id"],
        url=row["url"],
        canonical_url=row["canonical_url"],
        title=row["title"],
        tags=row["tags"] or [],
        status=row["status"],
        cluster_id=row["cluster_id"],
        cluster_label=row["cluster_label"],
        created_at=row["created_at"],
    )


@router.get(
    "/bookmarks",
    response_model=BookmarkListResponse,
    summary="List user bookmarks",
)
async def list_bookmarks(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get paginated list of user's bookmarks."""
    offset = (page - 1) * page_size
    
    # Get total count
    total = await db.fetchval(
        "SELECT COUNT(*) FROM bookmarks WHERE user_id = $1",
        user.id
    )
    
    # Get bookmarks
    rows = await db.fetch(
        """
        SELECT id, url, canonical_url, title, tags, status,
               cluster_id, cluster_label, created_at
        FROM bookmarks
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        user.id, page_size, offset
    )
    
    items = [
        BookmarkResponse(
            id=row["id"],
            url=row["url"],
            canonical_url=row["canonical_url"],
            title=row["title"],
            tags=row["tags"] or [],
            status=row["status"],
            cluster_id=row["cluster_id"],
            cluster_label=row["cluster_label"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    
    total_pages = (total + page_size - 1) // page_size
    
    return BookmarkListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/bookmarks/{bookmark_id}",
    response_model=BookmarkDetail,
    summary="Get bookmark details",
)
async def get_bookmark(
    bookmark_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Get detailed information about a specific bookmark."""
    row = await db.fetchrow(
        """
        SELECT id, url, canonical_url, title, summary, tags, status,
               cluster_id, cluster_label, created_at, updated_at, embedded_at
        FROM bookmarks
        WHERE id = $1 AND user_id = $2
        """,
        bookmark_id, user.id
    )
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bookmark not found",
        )
    
    return BookmarkDetail(
        id=row["id"],
        url=row["url"],
        canonical_url=row["canonical_url"],
        title=row["title"],
        summary=row["summary"],
        tags=row["tags"] or [],
        status=row["status"],
        cluster_id=row["cluster_id"],
        cluster_label=row["cluster_label"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        embedded_at=row["embedded_at"],
    )


@router.delete(
    "/bookmarks/{bookmark_id}",
    response_model=MessageResponse,
    summary="Delete a bookmark",
)
async def delete_bookmark(
    bookmark_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Delete a bookmark."""
    result = await db.execute(
        "DELETE FROM bookmarks WHERE id = $1 AND user_id = $2",
        bookmark_id, user.id
    )
    
    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bookmark not found",
        )
    
    logger.info("Bookmark deleted", bookmark_id=str(bookmark_id), user_id=str(user.id))
    
    return MessageResponse(message="Bookmark deleted successfully")
