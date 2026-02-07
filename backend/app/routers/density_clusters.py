"""
Density (HDBSCAN) cluster API endpoints.
Reads from clusters table + bookmarks.cluster_id (populated by batch job).
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
import structlog

from app.auth import get_current_user, CurrentUser
from app.models import (
    BookmarkResponse,
    DensityClusterResponse,
    DensityClusterListResponse,
    DensityClusterDetail,
)
from app import database as db

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/density-clusters",
    response_model=DensityClusterListResponse,
    summary="List user density (HDBSCAN) clusters",
)
async def list_density_clusters(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100, description="Max clusters to return")] = 40,
    min_size: Annotated[int, Query(ge=1, description="Minimum group size")] = 1,
):
    """Get HDBSCAN clusters for the current user from the clusters table."""
    rows = await db.fetch(
        """
        SELECT id, label, size, updated_at
        FROM clusters
        WHERE user_id = $1 AND size >= $2
        ORDER BY size DESC, updated_at DESC NULLS LAST
        LIMIT $3
        """,
        user.id,
        min_size,
        limit,
    )

    items = [
        DensityClusterResponse(
            id=str(row["id"]),
            label=row["label"] or None,
            size=row["size"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]

    return DensityClusterListResponse(items=items, total=len(items))


@router.get(
    "/density-clusters/{cluster_pk}",
    response_model=DensityClusterDetail,
    summary="Get density cluster details with bookmarks",
)
async def get_density_cluster(
    cluster_pk: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Get a density cluster (by clusters.id) with its bookmarks."""
    cluster_row = await db.fetchrow(
        """
        SELECT id, cluster_id, label, size
        FROM clusters
        WHERE id = $1 AND user_id = $2
        """,
        cluster_pk,
        user.id,
    )

    if not cluster_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cluster not found",
        )

    # Bookmarks with this user's cluster_id (integer) from clusters table
    bookmark_rows = await db.fetch(
        """
        SELECT b.id, b.url, b.canonical_url, b.title, b.tags, b.status, b.created_at
        FROM bookmarks b
        WHERE b.user_id = $1 AND b.cluster_id = $2
        ORDER BY b.created_at DESC
        """,
        user.id,
        cluster_row["cluster_id"],
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

    return DensityClusterDetail(
        id=str(cluster_row["id"]),
        label=cluster_row["label"] or None,
        size=cluster_row["size"],
        bookmarks=bookmarks,
    )
