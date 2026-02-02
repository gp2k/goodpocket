"""
Cluster API endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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
):
    """Get all clusters for the current user."""
    rows = await db.fetch(
        """
        SELECT cluster_id, label, size, updated_at
        FROM clusters
        WHERE user_id = $1
        ORDER BY size DESC
        """,
        user.id
    )
    
    items = [
        ClusterResponse(
            cluster_id=row["cluster_id"],
            label=row["label"],
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
    cluster_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Get a cluster with its bookmarks."""
    # Get cluster info
    cluster_row = await db.fetchrow(
        """
        SELECT cluster_id, label, size
        FROM clusters
        WHERE user_id = $1 AND cluster_id = $2
        """,
        user.id, cluster_id
    )
    
    if not cluster_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found",
        )
    
    # Get bookmarks in this cluster
    bookmark_rows = await db.fetch(
        """
        SELECT id, url, canonical_url, title, tags, status,
               cluster_id, cluster_label, created_at
        FROM bookmarks
        WHERE user_id = $1 AND cluster_id = $2
        ORDER BY created_at DESC
        """,
        user.id, cluster_id
    )
    
    bookmarks = [
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
        for row in bookmark_rows
    ]
    
    return ClusterDetail(
        cluster_id=cluster_row["cluster_id"],
        label=cluster_row["label"],
        size=cluster_row["size"],
        bookmarks=bookmarks,
    )
