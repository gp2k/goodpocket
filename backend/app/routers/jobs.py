"""
Batch job endpoints for embedding and clustering.
Protected by secret header for Cloud Scheduler.
"""
from fastapi import APIRouter, HTTPException, Header, status, BackgroundTasks
import structlog

from app.config import get_settings
from app.models import MessageResponse
from app.jobs.batch_processor import run_batch_job, regenerate_all_tags

logger = structlog.get_logger()

router = APIRouter()


@router.post(
    "/jobs/batch",
    response_model=MessageResponse,
    summary="Trigger batch embedding and clustering job",
    description="Protected endpoint for Cloud Scheduler. Requires X-Batch-Secret header.",
)
async def trigger_batch_job(
    background_tasks: BackgroundTasks,
    x_batch_secret: str = Header(..., alias="X-Batch-Secret"),
):
    """
    Trigger the batch job for:
    1. Generating embeddings for pending bookmarks
    2. Running clustering for all users
    """
    settings = get_settings()
    
    # Validate secret
    if not settings.batch_job_secret or x_batch_secret != settings.batch_job_secret:
        logger.warning("Invalid batch job secret attempt")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid batch secret",
        )
    
    logger.info("Batch job triggered")
    
    # Run in background to avoid timeout
    background_tasks.add_task(run_batch_job)
    
    return MessageResponse(message="Batch job started")


@router.post(
    "/jobs/batch/sync",
    response_model=MessageResponse,
    summary="Run batch job synchronously (for testing)",
    include_in_schema=False,  # Hide from docs
)
async def trigger_batch_job_sync(
    x_batch_secret: str = Header(..., alias="X-Batch-Secret"),
):
    """Run batch job synchronously for testing."""
    settings = get_settings()
    
    if not settings.batch_job_secret or x_batch_secret != settings.batch_job_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid batch secret",
        )
    
    logger.info("Batch job (sync) triggered")
    await run_batch_job()
    
    return MessageResponse(message="Batch job completed")


@router.post(
    "/jobs/regenerate-tags",
    response_model=MessageResponse,
    summary="Regenerate tags for all bookmarks",
    description="Regenerates tags for all existing bookmarks using the improved algorithm.",
)
async def trigger_regenerate_tags(
    x_batch_secret: str = Header(..., alias="X-Batch-Secret"),
):
    """
    Regenerate tags for all bookmarks using the improved tag extraction algorithm.
    
    This uses:
    - Korean morphological analysis (Kiwi) for Korean content
    - YAKE for English content
    - Tech term boosting for relevant keywords
    """
    settings = get_settings()
    
    if not settings.batch_job_secret or x_batch_secret != settings.batch_job_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid batch secret",
        )
    
    logger.info("Tag regeneration triggered")
    result = await regenerate_all_tags()
    
    return MessageResponse(
        message=f"Tag regeneration completed: {result['updated']} updated, {result['failed']} failed, {result['skipped']} skipped"
    )
