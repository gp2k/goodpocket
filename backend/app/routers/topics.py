"""
Topics tree API (tag-based hierarchical categories).
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
import structlog

from app.auth import get_current_user, CurrentUser
from app.models import TopicTreeEntry
from app import database as db

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/topics/tree",
    response_model=TopicTreeEntry,
    summary="Get hierarchical topic tree",
)
async def get_topics_tree(
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Return tag-based topic tree: root -> Level1 tags -> Level2 (co-occurring) tags; each node has dup_group_count and dup_group_ids."""
    rows = await db.fetch(
        """
        SELECT id, parent_id, label
        FROM topics
        WHERE user_id = $1
        """,
        user.id,
    )
    if not rows:
        return TopicTreeEntry(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            label="전체",
            children=[],
            dup_group_count=0,
            dup_group_ids=[],
        )

    # dup_group counts and ids per topic_id
    count_rows = await db.fetch(
        """
        SELECT topic_id, COUNT(*) AS cnt, array_agg(dup_group_id) AS ids
        FROM dup_group_topics
        WHERE dup_group_id IN (SELECT id FROM dup_groups WHERE user_id = $1)
        GROUP BY topic_id
        """,
        user.id,
    )
    topic_counts: dict = {}
    topic_ids_list: dict = {}
    for r in count_rows:
        topic_counts[str(r["topic_id"])] = r["cnt"]
        topic_ids_list[str(r["topic_id"])] = list(r["ids"] or [])

    by_parent: dict = {}
    topic_by_id: dict = {}
    for r in rows:
        tid = str(r["id"])
        pid = str(r["parent_id"]) if r["parent_id"] else None
        topic_by_id[tid] = {
            "id": r["id"],
            "label": r["label"] or "",
            "dup_group_count": topic_counts.get(tid, 0),
            "dup_group_ids": topic_ids_list.get(tid, []),
        }
        by_parent.setdefault(pid, []).append(tid)

    def build_node(topic_id: str) -> TopicTreeEntry:
        t = topic_by_id[topic_id]
        child_ids = by_parent.get(topic_id, [])
        return TopicTreeEntry(
            id=t["id"],
            label=t["label"],
            children=[build_node(cid) for cid in child_ids],
            dup_group_count=t["dup_group_count"],
            dup_group_ids=t["dup_group_ids"],
        )

    root_ids = by_parent.get(None, [])
    if not root_ids:
        return TopicTreeEntry(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            label="전체",
            children=[],
            dup_group_count=0,
            dup_group_ids=[],
        )
    root_id = root_ids[0]
    return build_node(root_id)
