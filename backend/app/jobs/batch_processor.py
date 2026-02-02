"""
Batch processor for embedding generation and clustering.
Runs periodically (every 3 hours) via Cloud Scheduler.
"""
from datetime import datetime
from typing import List, Dict, Any
from uuid import UUID

import structlog

from app import database as db
from app.services.embedding import generate_embeddings_batch, create_embedding_text
from app.services.clustering import cluster_user_bookmarks, generate_cluster_labels
from app.services.tag_generator import generate_tags

logger = structlog.get_logger()

# Batch sizes
EMBEDDING_BATCH_SIZE = 50
CLUSTERING_MIN_BOOKMARKS = 5  # Minimum bookmarks needed to cluster


async def run_batch_job() -> Dict[str, Any]:
    """
    Run the complete batch job:
    1. Generate embeddings for pending bookmarks
    2. Run clustering for all users with sufficient bookmarks
    
    Returns:
        Summary statistics of the batch job
    """
    logger.info("Starting batch job")
    start_time = datetime.utcnow()
    
    stats = {
        "embeddings_processed": 0,
        "embeddings_failed": 0,
        "users_clustered": 0,
        "errors": [],
    }
    
    try:
        # Step 1: Generate embeddings
        embedding_stats = await process_pending_embeddings()
        stats["embeddings_processed"] = embedding_stats["processed"]
        stats["embeddings_failed"] = embedding_stats["failed"]
        
        # Step 2: Run clustering
        clustering_stats = await run_clustering_for_all_users()
        stats["users_clustered"] = clustering_stats["users_processed"]
        
    except Exception as e:
        logger.error("Batch job failed", error=str(e), exc_info=True)
        stats["errors"].append(str(e))
    
    duration = (datetime.utcnow() - start_time).total_seconds()
    logger.info(
        "Batch job completed",
        duration_seconds=duration,
        **stats
    )
    
    return stats


async def process_pending_embeddings() -> Dict[str, int]:
    """
    Process all bookmarks with pending embeddings.
    
    Returns:
        Statistics: {"processed": N, "failed": N}
    """
    logger.info("Processing pending embeddings")
    
    processed = 0
    failed = 0
    
    while True:
        # Fetch a batch of pending bookmarks
        rows = await db.fetch(
            """
            SELECT id, title, tags, summary
            FROM bookmarks
            WHERE status = 'pending_embedding'
            ORDER BY created_at ASC
            LIMIT $1
            """,
            EMBEDDING_BATCH_SIZE
        )
        
        if not rows:
            break
        
        logger.info(f"Processing batch of {len(rows)} bookmarks")
        
        # Prepare texts for embedding
        bookmark_ids = []
        texts = []
        
        for row in rows:
            bookmark_ids.append(row["id"])
            text = create_embedding_text(
                title=row["title"] or "",
                tags=row["tags"] or [],
                summary=row["summary"] or "",
            )
            texts.append(text)
        
        # Generate embeddings
        embeddings = await generate_embeddings_batch(texts)
        
        # Update database
        for bookmark_id, embedding in zip(bookmark_ids, embeddings):
            try:
                if embedding:
                    await db.execute(
                        """
                        UPDATE bookmarks
                        SET embedding = $1,
                            status = 'embedded',
                            embedded_at = NOW()
                        WHERE id = $2
                        """,
                        embedding,
                        bookmark_id
                    )
                    processed += 1
                else:
                    await db.execute(
                        """
                        UPDATE bookmarks
                        SET status = 'failed'
                        WHERE id = $1
                        """,
                        bookmark_id
                    )
                    failed += 1
                    
            except Exception as e:
                logger.error(
                    "Failed to update bookmark embedding",
                    bookmark_id=str(bookmark_id),
                    error=str(e)
                )
                failed += 1
    
    logger.info(
        "Embedding processing completed",
        processed=processed,
        failed=failed
    )
    
    return {"processed": processed, "failed": failed}


async def run_clustering_for_all_users() -> Dict[str, int]:
    """
    Run clustering for all users with sufficient bookmarks.
    
    Returns:
        Statistics: {"users_processed": N}
    """
    logger.info("Running clustering for all users")
    
    # Get all users with enough embedded bookmarks
    user_rows = await db.fetch(
        """
        SELECT DISTINCT user_id, COUNT(*) as bookmark_count
        FROM bookmarks
        WHERE status = 'embedded' AND embedding IS NOT NULL
        GROUP BY user_id
        HAVING COUNT(*) >= $1
        """,
        CLUSTERING_MIN_BOOKMARKS
    )
    
    users_processed = 0
    
    for user_row in user_rows:
        user_id = user_row["user_id"]
        bookmark_count = user_row["bookmark_count"]
        
        try:
            await cluster_user(user_id, bookmark_count)
            users_processed += 1
        except Exception as e:
            logger.error(
                "Failed to cluster user bookmarks",
                user_id=str(user_id),
                error=str(e),
                exc_info=True
            )
    
    logger.info("Clustering completed", users_processed=users_processed)
    
    return {"users_processed": users_processed}


async def cluster_user(user_id: UUID, bookmark_count: int) -> None:
    """
    Run clustering for a single user.
    
    Args:
        user_id: User to cluster
        bookmark_count: Number of bookmarks (for logging)
    """
    logger.info(
        "Clustering user bookmarks",
        user_id=str(user_id),
        bookmark_count=bookmark_count
    )
    
    # Fetch all embedded bookmarks for user
    rows = await db.fetch(
        """
        SELECT id, embedding, tags
        FROM bookmarks
        WHERE user_id = $1 AND status = 'embedded' AND embedding IS NOT NULL
        """,
        user_id
    )
    
    if len(rows) < CLUSTERING_MIN_BOOKMARKS:
        logger.info("Not enough bookmarks for clustering", user_id=str(user_id))
        return
    
    # Prepare data
    bookmark_ids = [row["id"] for row in rows]
    embeddings = [row["embedding"] for row in rows]
    tags_list = [row["tags"] or [] for row in rows]
    
    # Run clustering
    cluster_assignments = await cluster_user_bookmarks(embeddings)
    
    if not cluster_assignments:
        logger.warning("Clustering returned no results", user_id=str(user_id))
        return
    
    # Generate labels for each cluster
    cluster_labels = generate_cluster_labels(cluster_assignments, tags_list)
    
    # Update bookmarks with cluster info
    cluster_version = datetime.utcnow()
    
    for bookmark_id, cluster_id in zip(bookmark_ids, cluster_assignments):
        label = cluster_labels.get(cluster_id)
        
        await db.execute(
            """
            UPDATE bookmarks
            SET cluster_id = $1,
                cluster_label = $2
            WHERE id = $3
            """,
            cluster_id if cluster_id >= 0 else None,  # -1 = noise
            label,
            bookmark_id
        )
    
    # Update clusters table
    # First, delete old clusters for user
    await db.execute(
        "DELETE FROM clusters WHERE user_id = $1",
        user_id
    )
    
    # Count cluster sizes
    cluster_sizes: Dict[int, int] = {}
    for cluster_id in cluster_assignments:
        if cluster_id >= 0:  # Skip noise (-1)
            cluster_sizes[cluster_id] = cluster_sizes.get(cluster_id, 0) + 1
    
    # Insert new clusters
    for cluster_id, size in cluster_sizes.items():
        label = cluster_labels.get(cluster_id)
        await db.execute(
            """
            INSERT INTO clusters (user_id, cluster_id, label, size, cluster_version)
            VALUES ($1, $2, $3, $4, $5)
            """,
            user_id,
            cluster_id,
            label,
            size,
            cluster_version
        )
    
    logger.info(
        "User clustering completed",
        user_id=str(user_id),
        clusters=len(cluster_sizes),
        noise_count=cluster_assignments.count(-1) if -1 in cluster_assignments else 0
    )


async def regenerate_all_tags() -> Dict[str, int]:
    """
    Regenerate tags for all existing bookmarks using the improved algorithm.
    
    This function fetches all bookmarks with title/summary and regenerates
    their tags using the new Korean-aware tag extraction algorithm.
    
    Returns:
        Statistics: {"updated": N, "failed": N, "skipped": N}
    """
    logger.info("Starting tag regeneration for all bookmarks")
    
    updated = 0
    failed = 0
    skipped = 0
    
    # Fetch all bookmarks with content
    rows = await db.fetch(
        """
        SELECT id, title, summary
        FROM bookmarks
        WHERE title IS NOT NULL OR summary IS NOT NULL
        ORDER BY created_at DESC
        """
    )
    
    logger.info(f"Found {len(rows)} bookmarks to process")
    
    for row in rows:
        bookmark_id = row["id"]
        title = row["title"] or ""
        summary = row["summary"] or ""
        
        # Skip if no content
        if not title and not summary:
            skipped += 1
            continue
        
        try:
            # Generate new tags
            new_tags = generate_tags(title=title, text=summary)
            
            # Update the bookmark
            await db.execute(
                """
                UPDATE bookmarks
                SET tags = $1
                WHERE id = $2
                """,
                new_tags,
                bookmark_id
            )
            updated += 1
            
            logger.debug(
                "Bookmark tags updated",
                bookmark_id=str(bookmark_id),
                tags_count=len(new_tags),
                tags=new_tags[:5]
            )
            
        except Exception as e:
            logger.error(
                "Failed to regenerate tags for bookmark",
                bookmark_id=str(bookmark_id),
                error=str(e)
            )
            failed += 1
    
    logger.info(
        "Tag regeneration completed",
        updated=updated,
        failed=failed,
        skipped=skipped
    )
    
    return {"updated": updated, "failed": failed, "skipped": skipped}
