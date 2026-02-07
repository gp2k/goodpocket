"""
마이그레이션 진행 상황을 DB에서 직접 조회합니다.

다른 터미널에서 실행 (진행 상황만 볼 때):
  cd backend
  $env:PYTHONIOENCODING = "utf-8"
  .\\.venv\\Scripts\\Activate.ps1
  python scripts/check_migration_progress.py

반복 조회: while ($true) { python scripts/check_migration_progress.py; Start-Sleep -Seconds 30 }
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import database as db

DEBUG_LOG = Path(__file__).resolve().parent.parent.parent / ".cursor" / "debug.log"


async def main() -> None:
    await db.init_db()
    try:
        # 전체 북마크
        total = await db.fetchval("SELECT COUNT(*) FROM bookmarks")
        with_simhash = await db.fetchval(
            "SELECT COUNT(*) FROM bookmarks WHERE simhash64 IS NOT NULL"
        )
        with_tags = await db.fetchval(
            """
            SELECT COUNT(*) FROM bookmarks b
            WHERE EXISTS (SELECT 1 FROM bookmark_tags bt WHERE bt.bookmark_id = b.id)
            """
        )
        # #region agent log
        empty_tags_col = await db.fetchval(
            "SELECT COUNT(*) FROM bookmarks WHERE tags = '{}' OR tags IS NULL"
        )
        has_bt_no_tags_col = await db.fetchval(
            """
            SELECT COUNT(*) FROM bookmarks b
            WHERE (b.tags = '{}' OR b.tags IS NULL)
              AND EXISTS (SELECT 1 FROM bookmark_tags bt WHERE bt.bookmark_id = b.id)
            """
        )
        try:
            DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(DEBUG_LOG, "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "hypothesisId": "H1",
                            "runId": "diagnostic",
                            "location": "check_migration_progress.py:main",
                            "message": "bookmarks.tags vs bookmark_tags counts",
                            "data": {
                                "total_bookmarks": total,
                                "empty_tags_column": empty_tags_col,
                                "has_bookmark_tags_but_empty_tags_column": has_bt_no_tags_col,
                            },
                            "timestamp": int(time.time() * 1000),
                        },
                        ensure_ascii=False,
                    ) + "\n"
                )
        except Exception:
            pass
        # #endregion
        # 미처리: simhash 없거나 bookmark_tags 없음
        pending = await db.fetchval(
            """
            SELECT COUNT(*) FROM bookmarks
            WHERE simhash64 IS NULL
               OR NOT EXISTS (SELECT 1 FROM bookmark_tags bt WHERE bt.bookmark_id = bookmarks.id)
            """
        )

        # dup_groups / bookmark_dup_map / topics
        dup_groups = await db.fetchval("SELECT COUNT(*) FROM dup_groups")
        dup_map_rows = await db.fetchval("SELECT COUNT(*) FROM bookmark_dup_map")
        topics_count = await db.fetchval("SELECT COUNT(*) FROM topics")

        print("=== 마이그레이션 진행 상황 ===")
        print(f"북마크 전체:        {total:,}")
        print(f"  simhash64 설정:   {with_simhash:,}  ({100*with_simhash/total:.1f}%)" if total else "  -")
        print(f"  bookmark_tags 있음: {with_tags:,}  ({100*with_tags/total:.1f}%)" if total else "  -")
        print(f"  미처리(남은 작업): {pending:,}")
        print()
        print(f"dup_groups:         {dup_groups:,}")
        print(f"bookmark_dup_map:   {dup_map_rows:,}")
        print(f"topics:             {topics_count:,}")
        print()

        # 사용자별 요약
        rows = await db.fetch(
            """
            SELECT
                b.user_id,
                COUNT(*) AS total,
                COUNT(b.id) FILTER (WHERE b.simhash64 IS NOT NULL) AS with_simhash,
                COUNT(b.id) FILTER (WHERE EXISTS (SELECT 1 FROM bookmark_tags bt WHERE bt.bookmark_id = b.id)) AS with_tags,
                (SELECT COUNT(*) FROM dup_groups dg WHERE dg.user_id = b.user_id) AS dup_groups
            FROM bookmarks b
            GROUP BY b.user_id
            ORDER BY total DESC
            """
        )
        print("=== 사용자별 요약 ===")
        for r in rows:
            uid = str(r["user_id"])[:8] + "..."
            total_u = r["total"] or 0
            sim_u = r["with_simhash"] or 0
            tags_u = r["with_tags"] or 0
            dg_u = r["dup_groups"] or 0
            pct = 100 * sim_u / total_u if total_u else 0
            print(f"  {uid}  북마크: {total_u:,}  simhash: {sim_u:,} ({pct:.0f}%)  tags: {tags_u:,}  dup_groups: {dg_u:,}")
    finally:
        await db.close_db()


if __name__ == "__main__":
    asyncio.run(main())
