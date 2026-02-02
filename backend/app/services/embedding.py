"""
Embedding service using sentence-transformers.
Generates 384-dimensional vectors using all-MiniLM-L6-v2 model.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List
import numpy as np

import structlog

from app.config import get_settings

logger = structlog.get_logger()

# Thread pool for CPU-bound embedding generation
_executor = ThreadPoolExecutor(max_workers=2)

# Global model instance (loaded lazily)
_model = None
_model_loading = False


def _load_model():
    """Load the sentence-transformer model (CPU-only)."""
    global _model, _model_loading
    
    if _model is not None:
        return _model
    
    if _model_loading:
        # Wait for another thread to finish loading
        import time
        while _model_loading and _model is None:
            time.sleep(0.1)
        return _model
    
    _model_loading = True
    
    try:
        from sentence_transformers import SentenceTransformer
        
        settings = get_settings()
        logger.info("Loading embedding model", model=settings.embedding_model_name)
        
        # Force CPU usage
        _model = SentenceTransformer(
            settings.embedding_model_name,
            device="cpu"
        )
        
        logger.info("Embedding model loaded successfully")
        return _model
        
    except Exception as e:
        logger.error("Failed to load embedding model", error=str(e))
        _model_loading = False
        raise


def _generate_embedding_sync(text: str) -> Optional[List[float]]:
    """
    Generate embedding synchronously (runs in thread pool).
    
    Args:
        text: Text to embed
        
    Returns:
        384-dimensional embedding as list of floats, or None on error
    """
    if not text or len(text.strip()) < 5:
        logger.warning("Text too short for embedding")
        return None
    
    try:
        model = _load_model()
        
        # Truncate very long text
        text = text[:2000]
        
        # Generate embedding
        embedding = model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
        )
        
        return embedding.tolist()
        
    except Exception as e:
        logger.error("Embedding generation failed", error=str(e))
        return None


def _generate_embeddings_batch_sync(texts: List[str]) -> List[Optional[List[float]]]:
    """
    Generate embeddings for multiple texts synchronously.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embeddings (or None for failed items)
    """
    if not texts:
        return []
    
    try:
        model = _load_model()
        
        # Truncate and filter texts
        processed_texts = []
        valid_indices = []
        
        for i, text in enumerate(texts):
            if text and len(text.strip()) >= 5:
                processed_texts.append(text[:2000])
                valid_indices.append(i)
        
        if not processed_texts:
            return [None] * len(texts)
        
        # Batch encode
        embeddings = model.encode(
            processed_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )
        
        # Map back to original indices
        results = [None] * len(texts)
        for i, embedding in zip(valid_indices, embeddings):
            results[i] = embedding.tolist()
        
        return results
        
    except Exception as e:
        logger.error("Batch embedding generation failed", error=str(e))
        return [None] * len(texts)


async def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generate embedding for a single text.
    
    Args:
        text: Text to embed
        
    Returns:
        384-dimensional embedding as list of floats, or None on error
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _generate_embedding_sync, text)


async def generate_embeddings_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """
    Generate embeddings for multiple texts in batch.
    
    More efficient than calling generate_embedding multiple times.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embeddings (same order as input, None for failed items)
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _generate_embeddings_batch_sync, texts)


def create_embedding_text(
    title: str = "",
    tags: List[str] = None,
    summary: str = "",
) -> str:
    """
    Create text for embedding from bookmark components.
    
    Format: "{title} {tags_joined} {summary}"
    
    Args:
        title: Bookmark title
        tags: List of tags
        summary: Content summary
        
    Returns:
        Combined text for embedding
    """
    parts = []
    
    if title:
        parts.append(title.strip())
    
    if tags:
        # Join tags with spaces (underscores already in tags)
        parts.append(" ".join(tags[:10]))
    
    if summary:
        # Use first 500 chars of summary
        parts.append(summary[:500].strip())
    
    return " ".join(parts)
