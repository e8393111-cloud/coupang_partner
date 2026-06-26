"""SQLite 저장소 — 콘텐츠·게시·성과를 추적한다.

posts 는 플랫폼 단위(콘텐츠×플랫폼)로, subId·딥링크·게시본문·예약시각을 함께
저장해 게시 큐 export 와 파트너스 리포트 import(성과 수집)를 자급한다.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .models import ContentPiece

_SCHEMA = """
CREATE TABLE IF NOT EXISTS content (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  TEXT NOT NULL,
    name        TEXT NOT NULL,
    price       INTEGER NOT NULL,
    category    TEXT,
    deeplink    TEXT NOT NULL,
    sub_id      TEXT NOT NULL,
    payload     TEXT NOT NULL,
    score       REAL,
    score_reasons TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS posts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id   INTEGER NOT NULL REFERENCES content(id),
    platform     TEXT NOT NULL,
    sub_id       TEXT,
    deeplink     TEXT,
    caption      TEXT,
    status       TEXT NOT NULL DEFAULT 'draft',  -- draft | scheduled | posted
    scheduled_at TEXT,
    posted_url   TEXT,
    clicks       INTEGER NOT NULL DEFAULT 0,
    orders       INTEGER NOT NULL DEFAULT 0,
    revenue      INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Storage:
    def __init__(self, path: str = "kupas.db") -> None:
        self.path = path
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # 저장
    # ------------------------------------------------------------------ #
    def save_content(self, piece: ContentPiece) -> int:
        score_total = piece.score.total if piece.score else None
        score_reasons = (
            "; ".join(piece.score.reasons) if piece.score and piece.score.reasons else None
        )
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO content "
                "(product_id, name, price, category, deeplink, sub_id, payload, score, score_reasons) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    piece.product.product_id,
                    piece.product.name,
                    piece.product.price,
                    piece.product.category_name,
                    piece.deeplink,
                    piece.sub_id,
                    json.dumps(piece.to_dict(), ensure_ascii=False),
                    score_total,
                    score_reasons,
                ),
            )
            content_id = int(cur.lastrowid)
            for cap in piece.captions:
                c.execute(
                    "INSERT INTO posts (content_id, platform, sub_id, deeplink, caption) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        content_id,
                        cap.platform,
                        piece.platform_subids.get(cap.platform),
                        piece.platform_links.get(cap.platform),
                        piece.rendered.get(cap.platform),
                    ),
                )
            return content_id

    # ------------------------------------------------------------------ #
    # 게시 상태
    # ------------------------------------------------------------------ #
    def schedule_post(self, post_id: int, when: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE posts SET status='scheduled', scheduled_at=? WHERE id=?",
                (when, post_id),
            )

    def mark_posted(self, post_id: int, posted_url: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE posts SET status='posted', posted_url=? WHERE id=?",
                (posted_url, post_id),
            )

    def list_due(self, now: str | None = None) -> list[dict]:
        """게시 대기(draft/scheduled) 중 예약시각이 지난 게시물 — 큐."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM posts WHERE status IN ('draft','scheduled') "
                "AND (scheduled_at IS NULL OR scheduled_at <= COALESCE(?, datetime('now'))) "
                "ORDER BY scheduled_at IS NULL, scheduled_at, id",
                (now,),
            ).fetchall()
            return [dict(r) for r in rows]

    def export_queue(self, now: str | None = None) -> list[dict]:
        """스케줄러(Make/Buffer 등)로 넘길 게시 패킷."""
        out = []
        for r in self.list_due(now):
            out.append({
                "post_id": r["id"],
                "platform": r["platform"],
                "caption": r["caption"],
                "deeplink": r["deeplink"],
                "sub_id": r["sub_id"],
                "scheduled_at": r["scheduled_at"],
            })
        return out

    # ------------------------------------------------------------------ #
    # 성과 수집
    # ------------------------------------------------------------------ #
    def record_performance(
        self, post_id: int, clicks: int = 0, orders: int = 0, revenue: int = 0
    ) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE posts SET clicks=clicks+?, orders=orders+?, revenue=revenue+? WHERE id=?",
                (clicks, orders, revenue, post_id),
            )

    def import_report(self, report: dict[str, dict]) -> int:
        """파트너스 리포트({subId: {clicks,orders,revenue}})를 subId 매칭으로 반영.

        리포트는 누적값이므로 덮어쓴다. 반영된 post 수를 반환.
        """
        updated = 0
        with self._conn() as c:
            for sub_id, perf in report.items():
                cur = c.execute(
                    "UPDATE posts SET clicks=?, orders=?, revenue=? WHERE sub_id=?",
                    (
                        int(perf.get("clicks", 0)),
                        int(perf.get("orders", 0)),
                        int(perf.get("revenue", 0)),
                        sub_id,
                    ),
                )
                updated += cur.rowcount
        return updated

    # ------------------------------------------------------------------ #
    # 조회
    # ------------------------------------------------------------------ #
    def list_content(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM content ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def list_posts(self, content_id: int | None = None) -> list[dict]:
        with self._conn() as c:
            if content_id is None:
                rows = c.execute("SELECT * FROM posts ORDER BY created_at DESC").fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM posts WHERE content_id=? ORDER BY platform", (content_id,)
                ).fetchall()
            return [dict(r) for r in rows]

    def summary(self) -> dict[str, int]:
        with self._conn() as c:
            row = c.execute(
                "SELECT COUNT(*) AS posts, "
                "COALESCE(SUM(clicks),0) AS clicks, "
                "COALESCE(SUM(orders),0) AS orders, "
                "COALESCE(SUM(revenue),0) AS revenue FROM posts"
            ).fetchone()
            return dict(row)
