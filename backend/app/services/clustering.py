"""
Clustering service using HDBSCAN with UMAP dimensionality reduction.
Falls back to simple cosine-threshold clustering if HDBSCAN fails.
"""
import asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional

import numpy as np
import structlog

from app.config import get_settings

logger = structlog.get_logger()

# Thread pool for CPU-bound clustering
_executor = ThreadPoolExecutor(max_workers=2)


def _cluster_with_hdbscan(
    embeddings: np.ndarray,
    min_cluster_size: int,
    umap_n_components: int,
    umap_n_neighbors: int,
) -> List[int]:
    """
    Cluster embeddings using UMAP + HDBSCAN.
    
    Args:
        embeddings: Array of shape (n_samples, n_features)
        min_cluster_size: Minimum cluster size for HDBSCAN
        umap_n_components: Target dimensions for UMAP
        umap_n_neighbors: Number of neighbors for UMAP
        
    Returns:
        List of cluster assignments (-1 for noise)
    """
    import umap
    import hdbscan
    
    n_samples = embeddings.shape[0]
    
    # Adjust UMAP parameters for small datasets
    actual_n_neighbors = min(umap_n_neighbors, n_samples - 1)
    actual_n_components = min(umap_n_components, n_samples - 1, embeddings.shape[1])
    
    if n_samples < 5:
        # Too few samples for meaningful clustering
        return [0] * n_samples
    
    logger.info(
        "Running UMAP dimensionality reduction",
        n_samples=n_samples,
        n_components=actual_n_components,
        n_neighbors=actual_n_neighbors
    )
    
    # UMAP reduction
    reducer = umap.UMAP(
        n_components=actual_n_components,
        n_neighbors=actual_n_neighbors,
        min_dist=0.0,
        metric="cosine",
        random_state=42,
    )
    
    reduced = reducer.fit_transform(embeddings)
    
    # Adjust HDBSCAN parameters
    actual_min_cluster_size = min(min_cluster_size, max(2, n_samples // 3))
    
    logger.info(
        "Running HDBSCAN clustering",
        min_cluster_size=actual_min_cluster_size
    )
    
    # HDBSCAN clustering
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=actual_min_cluster_size,
        min_samples=1,
        metric="euclidean",
        cluster_selection_method="eom",
    )
    
    labels = clusterer.fit_predict(reduced)
    
    return labels.tolist()


def _cluster_with_cosine_threshold(
    embeddings: np.ndarray,
    threshold: float = 0.7,
) -> List[int]:
    """
    Simple clustering using cosine similarity threshold.
    Uses connected components on a similarity graph.
    
    Args:
        embeddings: Array of shape (n_samples, n_features)
        threshold: Similarity threshold for connecting nodes
        
    Returns:
        List of cluster assignments
    """
    from sklearn.metrics.pairwise import cosine_similarity
    
    n_samples = embeddings.shape[0]
    
    if n_samples < 2:
        return [0] * n_samples
    
    # Compute similarity matrix
    similarity = cosine_similarity(embeddings)
    
    # Build adjacency list based on threshold
    adjacency = [[] for _ in range(n_samples)]
    for i in range(n_samples):
        for j in range(i + 1, n_samples):
            if similarity[i, j] >= threshold:
                adjacency[i].append(j)
                adjacency[j].append(i)
    
    # Find connected components using BFS
    labels = [-1] * n_samples
    current_label = 0
    
    for start in range(n_samples):
        if labels[start] != -1:
            continue
        
        # BFS from this node
        queue = [start]
        while queue:
            node = queue.pop(0)
            if labels[node] != -1:
                continue
            
            labels[node] = current_label
            
            for neighbor in adjacency[node]:
                if labels[neighbor] == -1:
                    queue.append(neighbor)
        
        current_label += 1
    
    return labels


def _cluster_sync(embeddings_list: List[List[float]]) -> List[int]:
    """
    Run clustering synchronously.
    
    Args:
        embeddings_list: List of embedding vectors
        
    Returns:
        List of cluster assignments
    """
    if not embeddings_list:
        return []
    
    settings = get_settings()
    embeddings = np.array(embeddings_list)
    
    try:
        # Try HDBSCAN first
        labels = _cluster_with_hdbscan(
            embeddings,
            min_cluster_size=settings.min_cluster_size,
            umap_n_components=settings.umap_n_components,
            umap_n_neighbors=settings.umap_n_neighbors,
        )
        
        logger.info(
            "HDBSCAN clustering successful",
            n_clusters=len(set(labels) - {-1}),
            noise_ratio=labels.count(-1) / len(labels) if labels else 0
        )
        
        return labels
        
    except Exception as e:
        logger.warning(
            "HDBSCAN clustering failed, falling back to cosine threshold",
            error=str(e)
        )
        
        # Fallback to simple cosine threshold clustering
        try:
            labels = _cluster_with_cosine_threshold(embeddings)
            logger.info(
                "Cosine threshold clustering successful",
                n_clusters=len(set(labels))
            )
            return labels
            
        except Exception as e2:
            logger.error("All clustering methods failed", error=str(e2))
            # Return all items in cluster 0
            return [0] * len(embeddings_list)


async def cluster_user_bookmarks(
    embeddings: List[List[float]],
) -> List[int]:
    """
    Cluster bookmarks based on their embeddings.
    
    Args:
        embeddings: List of bookmark embeddings
        
    Returns:
        List of cluster IDs (-1 for noise/unclustered)
    """
    if not embeddings:
        return []
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _cluster_sync, embeddings)


def generate_cluster_labels(
    cluster_assignments: List[int],
    tags_list: List[List[str]],
    top_n: int = 5,
) -> Dict[int, str]:
    """
    Generate labels for clusters based on most frequent tags.
    
    Args:
        cluster_assignments: List of cluster IDs for each bookmark
        tags_list: List of tags for each bookmark
        top_n: Number of top tags to include in label
        
    Returns:
        Dictionary mapping cluster_id to label string
    """
    # Group tags by cluster
    cluster_tags: Dict[int, List[str]] = {}
    
    for cluster_id, tags in zip(cluster_assignments, tags_list):
        if cluster_id < 0:  # Skip noise
            continue
        
        if cluster_id not in cluster_tags:
            cluster_tags[cluster_id] = []
        
        cluster_tags[cluster_id].extend(tags)
    
    # Generate labels from most common tags
    labels = {}
    
    for cluster_id, tags in cluster_tags.items():
        if not tags:
            labels[cluster_id] = f"Cluster {cluster_id}"
            continue
        
        # Count tag frequencies
        tag_counts = Counter(tags)
        
        # Get top N most common tags
        top_tags = [tag for tag, count in tag_counts.most_common(top_n)]
        
        # Create label
        labels[cluster_id] = ", ".join(top_tags)
    
    return labels
