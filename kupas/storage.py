"""SQLite 저장소 — 생성한 콘텐츠와 게시·성과를 추적한다."""

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
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id  INTEGER NOT NULL REFERENCES content(id),
    platform    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'draft',  -- draft | posted
    posted_url  TEXT,
    clicks      INTEGER NOT NULL DEFAULT 0,
    orders      INTEGER NOT NULL DEFAULT 0,
    revenue     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
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

    def save_content(self, piece: ContentPiece) -> int:
        """콘텐츠 1건과 플랫폼별 게시 초안(draft)을 저장하고 content id 를 반환."""
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
                    "INSERT INTO posts (content_id, platform) VALUES (?, ?)",
                    (content_id, cap.platform),
                )
            return content_id

    def mark_posted(self, post_id: int, posted_url: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE posts SET status='posted', posted_url=? WHERE id=?",
                (posted_url, post_id),
            )

    def record_performance(
        self, post_id: int, clicks: int = 0, orders: int = 0, revenue: int = 0
    ) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE posts SET clicks=clicks+?, orders=orders+?, revenue=revenue+? WHERE id=?",
                (clicks, orders, revenue, post_id),
            )

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
