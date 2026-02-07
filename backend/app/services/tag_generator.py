"""
Tag generation service using YAKE and Kiwi (Korean morphological analyzer).
Generates normalized hashtags from content with language-aware processing.
"""
import re
from collections import Counter
from typing import Optional, List, Set

import yake
import structlog
from kiwipiepy import Kiwi

from app.utils.korean_stopwords import (
    ALL_STOPWORDS, 
    is_stopword, 
    TECH_TERMS,
    TECH_TERMS_KOREAN,
)

logger = structlog.get_logger()

# Initialize Kiwi (Korean morphological analyzer)
_kiwi: Optional[Kiwi] = None

def get_kiwi() -> Kiwi:
    """Get or create Kiwi instance (lazy initialization)."""
    global _kiwi
    if _kiwi is None:
        _kiwi = Kiwi()
    return _kiwi


# YAKE configuration (for English content)
YAKE_LANGUAGE = "en"
YAKE_MAX_NGRAM = 1    # Single words only for cleaner tags
YAKE_DEDUP_LIM = 0.9
YAKE_TOP_N = 30

# Tag constraints
MIN_TAG_LENGTH_EN = 2
MIN_TAG_LENGTH_KO = 1  # Korean single character nouns can be meaningful
MAX_TAG_LENGTH = 24
MAX_TAGS = 15
MIN_TAGS = 5


def detect_language(text: str) -> str:
    """
    Detect primary language of text based on character ratio.
    
    Args:
        text: Text to analyze
        
    Returns:
        "ko" for Korean, "en" for English/other
    """
    if not text:
        return "en"
    
    korean_chars = sum(1 for c in text if '\uac00' <= c <= '\ud7a3')
    ratio = korean_chars / len(text) if len(text) > 0 else 0
    
    return "ko" if ratio > 0.2 else "en"


def _normalize_tag(tag: str, language: str = "en") -> Optional[str]:
    """
    Normalize a tag string.
    
    Rules:
    - Lowercase for English
    - Keep Korean as-is (no case change)
    - Replace whitespace with underscores
    - Remove special characters except underscores
    - Length constraints based on language
    
    Args:
        tag: Raw tag string
        language: "ko" or "en"
        
    Returns:
        Normalized tag or None if invalid
    """
    if not tag:
        return None
    
    # Strip whitespace
    tag = tag.strip()
    
    # Replace whitespace with underscores
    tag = re.sub(r"\s+", "_", tag)
    
    # Process each character
    result = []
    for char in tag:
        # Check if Korean character (Hangul)
        if "\uac00" <= char <= "\ud7a3" or "\u1100" <= char <= "\u11ff":
            result.append(char)
        # Check if alphanumeric or underscore
        elif char.isalnum() or char == "_":
            # Lowercase English letters
            if char.isalpha():
                result.append(char.lower())
            else:
                result.append(char)
    
    normalized = "".join(result)
    
    # Remove leading/trailing underscores and collapse multiple underscores
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    
    # Check length based on language
    min_len = MIN_TAG_LENGTH_KO if language == "ko" else MIN_TAG_LENGTH_EN
    if len(normalized) < min_len or len(normalized) > MAX_TAG_LENGTH:
        return None
    
    return normalized


def _is_valid_tag(tag: str) -> bool:
    """
    Check if a normalized tag is valid.
    
    Args:
        tag: Normalized tag string
        
    Returns:
        True if valid
    """
    if not tag:
        return False
    
    # Check if it's a stopword
    if is_stopword(tag):
        return False
    
    # Check for underscore-separated parts
    parts = tag.split("_")
    for part in parts:
        if part and is_stopword(part):
            # If all parts are stopwords, reject
            if all(is_stopword(p) for p in parts if p):
                return False
    
    # Check if mostly numbers
    alpha_count = sum(1 for c in tag if c.isalpha())
    if alpha_count < len(tag) * 0.3:  # At least 30% letters
        return False
    
    return True


def extract_korean_keywords(text: str, top_n: int = 30) -> List[str]:
    """
    Extract keywords from Korean text using Kiwi morphological analyzer.
    
    Extracts:
    - NNG: 일반명사 (common nouns)
    - NNP: 고유명사 (proper nouns)
    - SL: 외래어 (foreign words)
    - SH: 한자 (Chinese characters)
    
    Args:
        text: Korean text to analyze
        top_n: Maximum keywords to return
        
    Returns:
        List of keywords sorted by frequency
    """
    if not text or len(text) < 5:
        return []
    
    try:
        kiwi = get_kiwi()
        tokens = kiwi.tokenize(text)
        
        # Extract nouns and foreign words
        valid_tags = {'NNG', 'NNP', 'SL', 'SH'}
        words = []
        
        for token in tokens:
            if token.tag in valid_tags:
                word = token.form.strip()
                # Filter out single-character common nouns that are often meaningless
                if token.tag == 'NNG' and len(word) < 2:
                    continue
                if word:
                    words.append(word)
        
        # Count frequencies
        word_counts = Counter(words)
        
        # Return top N by frequency
        return [word for word, count in word_counts.most_common(top_n)]
        
    except Exception as e:
        logger.warning("Korean keyword extraction failed", error=str(e))
        return []


def extract_keywords_yake(text: str, top_n: int = YAKE_TOP_N) -> List[str]:
    """
    Extract keywords using YAKE (for English content).
    
    Args:
        text: Text to extract keywords from
        top_n: Number of keywords to extract
        
    Returns:
        List of keywords
    """
    if not text or len(text) < 10:
        return []
    
    try:
        kw_extractor = yake.KeywordExtractor(
            lan=YAKE_LANGUAGE,
            n=YAKE_MAX_NGRAM,
            dedupLim=YAKE_DEDUP_LIM,
            top=top_n,
            features=None,
        )
        
        keywords = kw_extractor.extract_keywords(text)
        return [kw for kw, score in keywords]
        
    except Exception as e:
        logger.warning("YAKE extraction failed", error=str(e))
        return []


def extract_tech_terms(text: str) -> List[str]:
    """
    Extract known tech terms from text.
    
    Args:
        text: Text to search in
        
    Returns:
        List of found tech terms
    """
    found = []
    text_lower = text.lower()
    
    # Check English tech terms (case-insensitive)
    for term in TECH_TERMS:
        # Use word boundary matching for short terms
        if len(term) <= 3:
            pattern = r'\b' + re.escape(term.lower()) + r'\b'
            if re.search(pattern, text_lower):
                found.append(term)
        else:
            if term.lower() in text_lower:
                found.append(term)
    
    # Check Korean tech terms
    for term in TECH_TERMS_KOREAN:
        if term in text:
            found.append(term)
    
    return found


def deduplicate_similar_tags(tags: List[str], threshold: float = 0.8) -> List[str]:
    """
    Remove similar tags based on overlap.
    
    Args:
        tags: List of tags
        threshold: Similarity threshold (0-1)
        
    Returns:
        Deduplicated list
    """
    if len(tags) <= 1:
        return tags
    
    result = []
    seen_bases = set()
    
    for tag in tags:
        # Get base form (remove common suffixes for Korean)
        base = tag.rstrip('의에서을를이가')
        
        # Check if we've seen a similar base
        is_duplicate = False
        for seen in seen_bases:
            # Simple overlap check
            if base in seen or seen in base:
                is_duplicate = True
                break
            # Check if one is a prefix of the other (>80% overlap)
            min_len = min(len(base), len(seen))
            if min_len > 2:
                overlap = sum(1 for a, b in zip(base, seen) if a == b)
                if overlap / min_len >= threshold:
                    is_duplicate = True
                    break
        
        if not is_duplicate:
            result.append(tag)
            seen_bases.add(base)
    
    return result


def generate_tags(
    title: str = "",
    text: str = "",
    max_tags: int = MAX_TAGS,
    min_tags: int = MIN_TAGS,
) -> List[str]:
    """
    Generate normalized tags from content.
    
    Process:
    1. Detect language
    2. Extract tech terms (priority)
    3. Extract keywords using appropriate method
    4. Normalize and validate
    5. Deduplicate and return
    
    Args:
        title: Content title (weighted higher)
        text: Content body text
        max_tags: Maximum number of tags to return
        min_tags: Minimum tags (will include less important ones if needed)
        
    Returns:
        List of normalized tag strings
    """
    # Combine title (weighted) + text
    combined_text = f"{title} {title} {title} {text}".strip()
    
    if len(combined_text) < 10:
        logger.info("Text too short for tag generation", length=len(combined_text))
        return []
    
    # Detect language
    language = detect_language(combined_text)
    logger.info("Language detected", language=language)
    
    # Collect all candidate tags
    candidates: List[str] = []
    
    # 1. Extract tech terms first (highest priority)
    tech_terms = extract_tech_terms(combined_text)
    candidates.extend(tech_terms)
    
    # 2. Extract keywords based on language
    if language == "ko":
        # Use Kiwi for Korean
        korean_keywords = extract_korean_keywords(combined_text)
        candidates.extend(korean_keywords)
        
        # Also try YAKE for any English parts
        english_keywords = extract_keywords_yake(combined_text)
        candidates.extend(english_keywords)
    else:
        # Use YAKE for English
        english_keywords = extract_keywords_yake(combined_text)
        candidates.extend(english_keywords)
    
    # 3. Process and normalize
    seen: Set[str] = set()
    tags: List[str] = []
    
    for keyword in candidates:
        normalized = _normalize_tag(keyword, language)
        
        if not normalized:
            continue
        
        if normalized.lower() in seen:
            continue
        
        if not _is_valid_tag(normalized):
            continue
        
        seen.add(normalized.lower())
        tags.append(normalized)
    
    # 4. Deduplicate similar tags
    tags = deduplicate_similar_tags(tags)
    
    # 5. Limit to max_tags
    tags = tags[:max_tags]
    
    # 6. If we don't have enough tags, try title only
    if len(tags) < min_tags and title:
        title_lang = detect_language(title)
        if title_lang == "ko":
            title_keywords = extract_korean_keywords(title, top_n=10)
        else:
            title_keywords = extract_keywords_yake(title, top_n=10)
        
        for keyword in title_keywords:
            normalized = _normalize_tag(keyword, title_lang)
            if normalized and normalized.lower() not in seen and _is_valid_tag(normalized):
                seen.add(normalized.lower())
                tags.append(normalized)
                if len(tags) >= min_tags:
                    break
    
    logger.info("Tags generated", count=len(tags), language=language)
    
    return tags
