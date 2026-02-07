"""
Simhash and duplicate-group logic for bookmark deduplication.
Used by the migration script and (later) the index API.
"""
import re
import hashlib
from typing import List, Dict, Any, Tuple
from uuid import UUID

import structlog

logger = structlog.get_logger()

# Hamming distance threshold for considering two simhashes as same bucket
SIMHASH_HAMMING_THRESHOLD = 3
# Shingle size (words)
SHINGLE_SIZE = 3


def _normalize_text(text: str) -> str:
    """Normalize text for simhash: lowercase, collapse whitespace."""
    if not text:
        return ""
    s = text.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _word_shingles(text: str, k: int = SHINGLE_SIZE) -> List[str]:
    """Split normalized text into word k-grams (shingles)."""
    words = text.split()
    if len(words) < k:
        return [" ".join(words)] if words else []
    return [" ".join(words[i : i + k]) for i in range(len(words) - k + 1)]


def _hash64(s: str) -> int:
    """Return 64-bit integer hash of string (unsigned, as Python int)."""
    h = hashlib.sha256(s.encode("utf-8")).digest()
    return int.from_bytes(h[:8], byteorder="big")


def compute_simhash(text: str) -> int:
    """
    Compute 64-bit simhash from text.
    Uses word shingles and bit-sign aggregation (standard simhash).
    """
    normalized = _normalize_text(text)
    if not normalized:
        return 0
    shingles = _word_shingles(normalized)
    if not shingles:
        return _hash64(normalized)  # fallback for very short text
    # 64-bit vector: for each bit position, sum +1 if shingle hash has 1, else -1
    v = [0] * 64
    for sh in shingles:
        h = _hash64(sh)
        for i in range(64):
            if (h >> i) & 1:
                v[i] += 1
            else:
                v[i] -= 1
    result = 0
    for i in range(64):
        if v[i] > 0:
            result |= 1 << i
    return result & ((1 << 64) - 1)  # keep 64 bits (non-negative in Py as int)


def _to_uint64(v: int) -> int:
    """Normalize to 64-bit unsigned (DB BIGINT can be signed)."""
    return int(v) & ((1 << 64) - 1)


def hamming_distance(a: int, b: int) -> int:
    """Number of bit positions where a and b differ (64-bit)."""
    # DB returns signed bigint; mask to 64 bits so shift loop terminates
    x = _to_uint64(a) ^ _to_uint64(b)
    n = 0
    while x:
        n += x & 1
        x >>= 1
    return n


def group_by_simhash(
    bookmark_rows: List[Dict[str, Any]],
    simhash_key: str = "simhash64",
    id_key: str = "id",
    created_at_key: str = "created_at",
    hamming_threshold: int = SIMHASH_HAMMING_THRESHOLD,
) -> List[Tuple[int, List[UUID], UUID]]:
    """
    Group bookmarks by simhash bucket (exact or Hamming distance <= threshold).
    Representative = first by created_at (newest) or first in list.

    Args:
        bookmark_rows: List of dicts with at least id, simhash64, created_at (optional).
        simhash_key: Key for simhash value (default "simhash64").
        id_key: Key for bookmark id (default "id").
        created_at_key: Key for created_at for picking representative (default "created_at").
        hamming_threshold: Merge groups with simhash within this Hamming distance (default 3).

    Returns:
        List of (simhash_bucket, [bookmark_id, ...], representative_id).
        representative_id is the bookmark id to use as dup_group representative.
    """
    if not bookmark_rows:
        return []

    # Build list of (simhash_uint64, id, created_at) — DB BIGINT is signed, normalize to 64-bit
    items: List[Tuple[int, UUID, Any]] = []
    for row in bookmark_rows:
        sh = row.get(simhash_key)
        if sh is None:
            continue
        bid = row.get(id_key)
        if bid is None:
            continue
        created = row.get(created_at_key)
        items.append((_to_uint64(int(sh)), UUID(str(bid)) if isinstance(bid, str) else bid, created))

    if not items:
        return []

    # Sort by created_at descending so newest is first (for representative)
    try:
        items.sort(key=lambda x: (x[2] is None, -(x[2].timestamp() if x[2] else 0)))
    except Exception:
        pass  # keep order if created_at not comparable

    # Union-find: merge groups with Hamming distance <= threshold
    parent: Dict[int, int] = {}  # simhash -> canonical simhash

    def find(s: int) -> int:
        if s not in parent:
            parent[s] = s
        if parent[s] != s:
            parent[s] = find(parent[s])
        return parent[s]

    def union(s1: int, s2: int) -> None:
        p1, p2 = find(s1), find(s2)
        if p1 != p2:
            parent[p1] = p2

    simhashes = list({x[0] for x in items})
    for i, s1 in enumerate(simhashes):
        for s2 in simhashes[i + 1 :]:
            if hamming_distance(s1, s2) <= hamming_threshold:
                union(s1, s2)  # merge groups when simhashes are close

    # Group by canonical simhash
    buckets: Dict[int, List[Tuple[int, UUID, Any]]] = {}
    for sh, bid, created in items:
        canonical = find(sh)
        if canonical not in buckets:
            buckets[canonical] = []
        buckets[canonical].append((sh, bid, created))

    result: List[Tuple[int, List[UUID], UUID]] = []
    for simhash_bucket, group in buckets.items():
        ids = [x[1] for x in group]
        representative_id = ids[0]  # already sorted by created_at desc
        result.append((simhash_bucket, ids, representative_id))

    return result
