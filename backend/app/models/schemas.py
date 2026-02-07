"""
Pydantic v2 schemas for API request/response models.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, ConfigDict


# =====================================================
# Request Schemas
# =====================================================

class BookmarkCreate(BaseModel):
    """Request schema for creating a new bookmark."""
    url: HttpUrl = Field(..., description="URL to bookmark")
    title: Optional[str] = Field(None, max_length=500, description="Optional title override")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://example.com/article",
                "title": "My Custom Title"
            }
        }
    )


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:
        """Calculate SQL offset."""
        return (self.page - 1) * self.page_size


# =====================================================
# Response Schemas
# =====================================================

class BookmarkResponse(BaseModel):
    """Basic bookmark response for list views."""
    id: UUID
    url: str
    canonical_url: Optional[str] = None
    title: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    status: str
    cluster_id: Optional[int] = None
    cluster_label: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class BookmarkDetail(BaseModel):
    """Detailed bookmark response with summary."""
    id: UUID
    url: str
    canonical_url: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    status: str
    cluster_id: Optional[int] = None
    cluster_label: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    embedded_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class BookmarkListResponse(BaseModel):
    """Paginated list of bookmarks."""
    items: list[BookmarkResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ClusterResponse(BaseModel):
    """Cluster (dup_group) summary for list views."""
    id: UUID
    label: Optional[str] = None
    size: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClusterListResponse(BaseModel):
    """List of clusters for a user."""
    items: list[ClusterResponse]
    total: int


class ClusterDetail(BaseModel):
    """Cluster (dup_group) with its bookmarks."""
    id: UUID
    label: Optional[str] = None
    size: int
    bookmarks: list[BookmarkResponse]


class TopicTreeEntry(BaseModel):
    """Hierarchical topic node for tree view (tag-based categories)."""
    id: UUID
    label: str
    children: list["TopicTreeEntry"] = Field(default_factory=list)
    dup_group_count: int = 0
    dup_group_ids: list[UUID] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


TopicTreeEntry.model_rebuild()


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"message": "Operation completed successfully"}
        }
    )


class ErrorResponse(BaseModel):
    """Error response."""
    detail: str
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"detail": "An error occurred"}
        }
    )
