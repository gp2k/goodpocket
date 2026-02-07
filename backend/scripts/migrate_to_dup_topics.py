"""
Migrate existing bookmarks to new clustering (dup_groups, topics, simhash, normalized tags).
Run after applying infra/migrations/003_dup_groups_topics_embeddings.sql.

Usage:
  python scripts/migrate_to_dup_topics.py [--user-id UUID] [--chunk-size N] [--dry-run] [--resume]
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import database as db
from app.services.dedup import compute_simhash, group_by_simhash
from app.services.tag_generator import detect_language, generate_tags, _normalize_tag

CHECKPOINT_FILE = Path(__file__).resolve().parent / ".migrate_dup_topics_checkpoint.json"
SUMMARY_TEXT_MAX = 2048

# Postgres BIGINT is signed int64; simhash is 64-bit unsigned
def _simhash_to_bigint(h: int | None) -> int | None:
    if h is None:
        return None
    return h if h < (1 << 63) else h - (1 << 64)


def _get_domain(url: str) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc or ""
        return netloc.strip().lower() or None
    except Exception:
        return None


def _summary_text(summary: str | None, excerpt: str | None) -> str:
    raw = (summary or "").strip() or (excerpt or "").strip()
    if not raw:
        return ""
    return raw[:SUMMARY_TEXT_MAX]


def load_checkpoint() -> dict:
    if not CHECKPOINT_FILE.exists():
        return {}
    try:
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_checkpoint(data: dict) -> None:
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


async def get_users_to_process(conn, only_user_id: str | None):
    if only_user_id:
        row = await conn.fetchrow(
            "SELECT user_id AS id FROM bookmarks WHERE user_id = $1 LIMIT 1",
            only_user_id,
        )
        if row:
            return [row["id"]]
        return []
    rows = await conn.fetch("SELECT DISTINCT user_id AS id FROM bookmarks ORDER BY id")
    return [r["id"] for r in rows]


async def backfill_bookmark_columns(conn, rows: list, dry_run: bool) -> int:
    updated = 0
    for row in rows:
        if row.get("simhash64") is not None:
            continue
        url = row.get("url") or ""
        title = (row.get("title") or "").strip()
        summary = row.get("summary")
        excerpt = row.get("extracted_text_excerpt")
        created_at = row.get("created_at")
        updated_at = row.get("updated_at")

        domain = _get_domain(url)
        fetched_at = updated_at or created_at
        summary_text = _summary_text(summary, excerpt)
        text_for_simhash = f"{title} {summary_text}".strip() or url
        simhash64 = compute_simhash(text_for_simhash) if text_for_simhash else None
        lang = detect_language(title + " " + summary_text) if (title or summary_text) else "en"
        row["summary_text"] = summary_text[:SUMMARY_TEXT_MAX] if summary_text else None
        row["lang"] = lang

        if dry_run:
            updated += 1
            continue
        await conn.execute(
            """
            UPDATE bookmarks
            SET domain = $1, fetched_at = $2, summary_text = $3, simhash64 = $4, lang = $5
            WHERE id = $6 AND (simhash64 IS NULL OR domain IS NULL)
            """,
            domain,
            fetched_at,
            summary_text[:SUMMARY_TEXT_MAX] if summary_text else None,
            _simhash_to_bigint(simhash64),
            lang,
            row["id"],
        )
        updated += 1
    return updated


def _row_to_dict(record) -> dict:
    return dict(record) if hasattr(record, "keys") else record


async def backfill_tags_for_chunk(conn, rows: list, dry_run: bool) -> int:
    """For each bookmark, ensure tags + bookmark_tags. Uses generate_tags if no tags."""
    count = 0
    for row in rows:
        if row.get("has_bookmark_tags") is True:
            continue
        user_id = row["user_id"]
        bookmark_id = row["id"]
        title = (row.get("title") or "").strip()
        summary_text = (row.get("summary_text") or row.get("summary") or row.get("extracted_text_excerpt") or "").strip()
        existing_tags = row.get("tags") or []

        if existing_tags and isinstance(existing_tags, list):
            tag_labels = []
            lang = row.get("lang") or "en"
            for t in existing_tags:
                if isinstance(t, str) and t.strip():
                    n = _normalize_tag(t.strip(), lang)
                    if n:
                        tag_labels.append(n)
            if not tag_labels:
                tag_labels = generate_tags(title=title, text=summary_text[:5000])
        else:
            tag_labels = generate_tags(title=title, text=summary_text[:5000])

        if dry_run:
            count += len(tag_labels)
            continue

        if tag_labels:
            for rank, label in enumerate(tag_labels):
                if not label:
                    continue
                # Upsert tag
                await conn.execute(
                    """
                    INSERT INTO tags (user_id, normalized_label)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id, normalized_label) DO NOTHING
                    """,
                    user_id,
                    label,
                )
                r = await conn.fetchrow(
                    "SELECT id FROM tags WHERE user_id = $1 AND normalized_label = $2",
                    user_id,
                    label,
                )
                if not r:
                    continue
                tag_id = r["id"]
                weight = 1.0 / (rank + 1) if rank < 20 else 0.05
                await conn.execute(
                    """
                    INSERT INTO bookmark_tags (bookmark_id, tag_id, weight)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (bookmark_id, tag_id) DO UPDATE SET weight = EXCLUDED.weight
                    """,
                    bookmark_id,
                    tag_id,
                    weight,
                )
                count += 1
        else:
            # 태그가 0개여도 "처리 완료"로 표시해 동일 북마크가 무한 재조회되지 않도록 함
            await _ensure_sentinel_tag_and_link(conn, user_id, bookmark_id)

    return count


# 태그가 없을 때만 사용. 북마크당 1회 삽입해 has_bookmark_tags가 True가 되도록 함
async def _ensure_sentinel_tag_and_link(conn, user_id, bookmark_id) -> None:
    sentinel_label = "__no_auto_tags__"
    await conn.execute(
        """
        INSERT INTO tags (user_id, normalized_label)
        VALUES ($1, $2)
        ON CONFLICT (user_id, normalized_label) DO NOTHING
        """,
        user_id,
        sentinel_label,
    )
    r = await conn.fetchrow(
        "SELECT id FROM tags WHERE user_id = $1 AND normalized_label = $2",
        user_id,
        sentinel_label,
    )
    if not r:
        return
    await conn.execute(
        """
        INSERT INTO bookmark_tags (bookmark_id, tag_id, weight)
        VALUES ($1, $2, 0)
        ON CONFLICT (bookmark_id, tag_id) DO NOTHING
        """,
        bookmark_id,
        r["id"],
    )


async def build_dup_groups_for_user(conn, user_id, dry_run: bool) -> int:
    print("    [dup_groups] Fetching bookmarks...", flush=True)
    rows = await conn.fetch(
        """
        SELECT id, user_id, simhash64, created_at
        FROM bookmarks
        WHERE user_id = $1 AND simhash64 IS NOT NULL
        ORDER BY created_at DESC NULLS LAST
        """,
        user_id,
    )
    if not rows:
        print("    [dup_groups] No bookmarks with simhash64, skip.", flush=True)
        return 0
    print(f"    [dup_groups] Fetched {len(rows)} bookmarks, grouping by simhash...", flush=True)
    bookmark_rows = [_row_to_dict(r) for r in rows]
    groups = group_by_simhash(bookmark_rows, simhash_key="simhash64", id_key="id", created_at_key="created_at")
    print(f"    [dup_groups] Got {len(groups)} groups, inserting...", flush=True)
    created = 0
    processed = 0
    for simhash_bucket, bookmark_ids, representative_id in groups:
        if dry_run:
            created += 1
            continue
        # Check if dup_group already exists for (user_id, simhash_bucket)
        existing = await conn.fetchrow(
            "SELECT id FROM dup_groups WHERE user_id = $1 AND simhash_bucket = $2",
            user_id,
            _simhash_to_bigint(simhash_bucket),
        )
        if existing:
            dup_group_id = existing["id"]
        else:
            dup_group_id = await conn.fetchval(
                """
                INSERT INTO dup_groups (user_id, representative_bookmark_id, size, simhash_bucket)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_id,
                representative_id,
                len(bookmark_ids),
                _simhash_to_bigint(simhash_bucket),
            )
            created += 1
        for bid in bookmark_ids:
            await conn.execute(
                """
                INSERT INTO bookmark_dup_map (bookmark_id, dup_group_id)
                VALUES ($1, $2)
                ON CONFLICT (bookmark_id, dup_group_id) DO NOTHING
                """,
                bid,
                dup_group_id,
            )
        processed += 1
        if processed % 500 == 0:
            print(f"    [dup_groups] Processed {processed}/{len(groups)} groups...", flush=True)
    return created


async def build_topics_for_user(conn, user_id, dry_run: bool) -> int:
    """Build topic tree: root -> domain topics; link dup_groups to domain topic."""
    print("    [topics] Resolving root topic...", flush=True)
    # Root topic per user
    root = await conn.fetchrow(
        "SELECT id FROM topics WHERE user_id = $1 AND parent_id IS NULL LIMIT 1",
        user_id,
    )
    if not root:
        if dry_run:
            return 1
        root_id = await conn.fetchval(
            "INSERT INTO topics (user_id, parent_id, label, metrics_json) VALUES ($1, NULL, $2, $3) RETURNING id",
            user_id,
            "전체",
            "{}",
        )
    else:
        root_id = root["id"]

    # Get all dup_groups for user with representative bookmark's domain
    print("    [topics] Fetching dup_groups with domain...", flush=True)
    rows = await conn.fetch(
        """
        SELECT dg.id AS dup_group_id, b.domain
        FROM dup_groups dg
        JOIN bookmarks b ON b.id = dg.representative_bookmark_id
        WHERE dg.user_id = $1 AND b.domain IS NOT NULL AND b.domain != ''
        """,
        user_id,
    )
    print(f"    [topics] Fetched {len(rows)} dup_groups, creating topic links...", flush=True)
    domain_to_topic: dict = {}
    created_topics = 0
    processed = 0
    for r in rows:
        domain = (r["domain"] or "").strip() or "unknown"
        if domain not in domain_to_topic:
            existing_topic = await conn.fetchrow(
                "SELECT id FROM topics WHERE user_id = $1 AND parent_id = $2 AND label = $3",
                user_id,
                root_id,
                domain,
            )
            if existing_topic:
                domain_to_topic[domain] = existing_topic["id"]
            else:
                if dry_run:
                    domain_to_topic[domain] = None
                    created_topics += 1
                    continue
                topic_id = await conn.fetchval(
                    "INSERT INTO topics (user_id, parent_id, label, metrics_json) VALUES ($1, $2, $3, $4) RETURNING id",
                    user_id,
                    root_id,
                    domain,
                    "{}",
                )
                domain_to_topic[domain] = topic_id
                created_topics += 1
        topic_id = domain_to_topic[domain]
        if topic_id and not dry_run:
            await conn.execute(
                """
                INSERT INTO dup_group_topics (dup_group_id, topic_id)
                VALUES ($1, $2)
                ON CONFLICT (dup_group_id, topic_id) DO NOTHING
                """,
                r["dup_group_id"],
                topic_id,
            )
        processed += 1
        if processed % 500 == 0:
            print(f"    [topics] Processed {processed}/{len(rows)} dup_groups...", flush=True)
    return created_topics


async def run_migration(
    only_user_id: str | None = None,
    chunk_size: int = 500,
    dry_run: bool = False,
    resume: bool = False,
) -> None:
    await db.init_db()
    pool = db.get_pool()
    checkpoint = load_checkpoint() if resume else {}
    last_completed_user_id = checkpoint.get("last_completed_user_id")

    async with pool.acquire() as conn:
        users = await get_users_to_process(conn, only_user_id)
        if not users:
            print("No users to process.", flush=True)
            return

        print(f"Users to process: {len(users)}", flush=True)
        for user_id in users:
            if resume and last_completed_user_id and str(user_id) <= str(last_completed_user_id):
                print(f"Skipping already-done user {user_id}", flush=True)
                continue

            print(f"Processing user {user_id}...", flush=True)

            while True:
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, url, title, summary, extracted_text_excerpt,
                           summary_text, lang, created_at, updated_at, tags, simhash64,
                           EXISTS (SELECT 1 FROM bookmark_tags bt WHERE bt.bookmark_id = bookmarks.id) AS has_bookmark_tags
                    FROM bookmarks
                    WHERE user_id = $1
                      AND (simhash64 IS NULL OR NOT EXISTS (SELECT 1 FROM bookmark_tags bt WHERE bt.bookmark_id = bookmarks.id))
                    ORDER BY created_at ASC
                    LIMIT $2
                    """,
                    user_id,
                    chunk_size,
                )
                if not rows:
                    break
                rows_list = [_row_to_dict(r) for r in rows]
                print(f"  [chunk] Fetched {len(rows_list)} unprocessed bookmarks, processing...", flush=True)
                try:
                    n_col = await backfill_bookmark_columns(conn, rows_list, dry_run)
                    print(f"  [chunk] Columns: {n_col} updated.", flush=True)
                    n_tags = await backfill_tags_for_chunk(conn, rows_list, dry_run)
                    print(f"  [chunk] Tags: {n_tags} links.", flush=True)
                except Exception as e:
                    print(f"Chunk error (user={user_id}, count={len(rows_list)}): {e}", flush=True)
                    raise
                if not dry_run:
                    pass  # checkpoint saved after user fully done
                print(f"  Backfilled chunk: {len(rows_list)} bookmarks", flush=True)

            print(f"  Building dup_groups and topics for user {user_id}...", flush=True)
            try:
                n_dg = await build_dup_groups_for_user(conn, user_id, dry_run)
                print(f"  Dup groups: {n_dg}", flush=True)
                n_t = await build_topics_for_user(conn, user_id, dry_run)
                print(f"  Topics (new): {n_t}", flush=True)
            except Exception as e:
                print(f"  Error building dup_groups/topics: {e}")
                raise
            if not dry_run:
                save_checkpoint({"last_completed_user_id": str(user_id)})
            print(f"  User {user_id} done.", flush=True)

    await db.close_db()
    print("Migration completed.", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Migrate bookmarks to dup_groups/topics")
    parser.add_argument("--user-id", type=str, help="Process only this user UUID")
    parser.add_argument("--chunk-size", type=int, default=500, help="Chunk size for bookmarks")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    args = parser.parse_args()
    asyncio.run(
        run_migration(
            only_user_id=args.user_id,
            chunk_size=args.chunk_size,
            dry_run=args.dry_run,
            resume=args.resume,
        )
    )


if __name__ == "__main__":
    main()
