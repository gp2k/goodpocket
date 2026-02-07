"""
Cluster API endpoints (dup_groups + bookmark_dup_map).
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
import structlog

from app.auth import get_current_user, CurrentUser
from app.models import (
    BookmarkResponse,
    ClusterResponse,
    ClusterListResponse,
    ClusterDetail,
)
from app import database as db

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/clusters",
    response_model=ClusterListResponse,
    summary="List user clusters",
)
async def list_clusters(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100, description="Max clusters to return")] = 40,
    min_size: Annotated[int, Query(ge=1, description="Minimum group size")] = 1,
):
    """Get dup_groups (clusters) for the current user, optionally limited and filtered by size."""
    rows = await db.fetch(
        """
        SELECT dg.id, dg.size, dg.updated_at,
               COALESCE(NULLIF(TRIM(b.title), ''), b.domain, 'Untitled') AS label
        FROM dup_groups dg
        LEFT JOIN bookmarks b ON b.id = dg.representative_bookmark_id
        WHERE dg.user_id = $1 AND dg.size >= $2
        ORDER BY dg.size DESC, dg.updated_at DESC NULLS LAST
        LIMIT $3
        """,
        user.id,
        min_size,
        limit,
    )

    items = [
        ClusterResponse(
            id=row["id"],
            label=row["label"] or "Untitled",
            size=row["size"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]

    return ClusterListResponse(items=items, total=len(items))


@router.get(
    "/clusters/{cluster_id}",
    response_model=ClusterDetail,
    summary="Get cluster details with bookmarks",
)
async def get_cluster(
    cluster_id: UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Get a dup_group (cluster) with its bookmarks."""
    cluster_row = await db.fetchrow(
        """
        SELECT dg.id, dg.size,
               COALESCE(NULLIF(TRIM(b.title), ''), b.domain, 'Untitled') AS label
        FROM dup_groups dg
        LEFT JOIN bookmarks b ON b.id = dg.representative_bookmark_id
        WHERE dg.user_id = $1 AND dg.id = $2
        """,
        user.id,
        cluster_id,
    )

    if not cluster_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found",
        )

    bookmark_rows = await db.fetch(
        """
        SELECT b.id, b.url, b.canonical_url, b.title, b.tags, b.status, b.created_at
        FROM bookmark_dup_map bdm
        JOIN bookmarks b ON b.id = bdm.bookmark_id
        WHERE bdm.dup_group_id = $1 AND b.user_id = $2
        ORDER BY b.created_at DESC
        """,
        cluster_id,
        user.id,
    )

    bookmarks = [
        BookmarkResponse(
            id=row["id"],
            url=row["url"],
            canonical_url=row["canonical_url"],
            title=row["title"],
            tags=row["tags"] or [],
            status=row["status"],
            cluster_id=None,
            cluster_label=None,
            created_at=row["created_at"],
        )
        for row in bookmark_rows
    ]

    return ClusterDetail(
        id=cluster_row["id"],
        label=cluster_row["label"] or "Untitled",
        size=cluster_row["size"],
        bookmarks=bookmarks,
    )
