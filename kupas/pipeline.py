"""호환 래퍼 — 기존 Pipeline API 를 새 에이전트 오케스트레이터에 위임한다.

신규 코드는 `kupas.agents.Orchestrator` + `Brief` 를 직접 쓰는 걸 권장.
"""

from __future__ import annotations

from .agents.base import Brief
from .agents.orchestrator import Orchestrator
from .agents.publish import DISCLOSURE  # 재노출(하위호환)
from .config import Config
from .models import ContentPiece

__all__ = ["Pipeline", "DISCLOSURE"]


class Pipeline:
    """발굴→선별→카피→게시준비를 한 번에 실행하는 얇은 래퍼."""

    def __init__(self, config: Config | None = None) -> None:
        self.orchestrator = Orchestrator(config)
        self.config = self.orchestrator.config
        self.storage = self.orchestrator.storage

    @property
    def mode_note(self) -> str:
        return self.orchestrator.mode_note

    def run(
        self,
        keyword: str | None = None,
        category_id: int | None = None,
        limit: int = 5,
        platforms: tuple[str, ...] = ("threads", "tiktok"),
        save: bool = True,
    ) -> list[ContentPiece]:
        brief = Brief(
            keyword=keyword,
            category_id=category_id,
            platforms=platforms,
            target_count=limit,
            shortlist_size=max(limit, 10),
        )
        return self.orchestrator.run(brief, save=save).pieces
