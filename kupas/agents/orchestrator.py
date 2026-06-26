"""오케스트레이터 — 4개 분야 에이전트를 Brief로 사슬 실행하고 로그를 모은다.

  DiscoveryAgent ─▶ CurationAgent ─▶ CopyAgent ─▶ PublishAgent
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..captions import CaptionGenerator
from ..config import Config
from ..coupang import CoupangClient
from ..models import ContentPiece, ScoredProduct
from ..storage import Storage
from .base import AgentLog, Brief
from .copy import CopyAgent
from .curation import CurationAgent, ScoreWeights
from .discovery import DiscoveryAgent
from .publish import PublishAgent


@dataclass
class OrchestrationResult:
    pieces: list[ContentPiece] = field(default_factory=list)
    shortlist: list[ScoredProduct] = field(default_factory=list)
    logs: list[AgentLog] = field(default_factory=list)


class Orchestrator:
    def __init__(self, config: Config | None = None, weights: ScoreWeights | None = None) -> None:
        self.config = config or Config.load()
        self.coupang = CoupangClient(
            self.config.coupang_access_key, self.config.coupang_secret_key
        )
        self.storage = Storage(self.config.db_path)

        # 발굴·선별이 공유하는 Claude 클라이언트(있을 때만)
        llm = None
        if self.config.has_anthropic:
            import anthropic

            llm = anthropic.Anthropic(api_key=self.config.anthropic_api_key)
        model = self.config.caption_model

        self.discovery = DiscoveryAgent(self.coupang, llm=llm, model=model)
        self.curation = CurationAgent(weights=weights, llm=llm, model=model)
        self.copy = CopyAgent(CaptionGenerator(self.config.anthropic_api_key, model))
        self.publish = PublishAgent(self.coupang, self.config.subid_prefix)

    @property
    def mode_note(self) -> str:
        return (
            "쿠팡=" + ("실 API" if not self.coupang.is_mock else "mock")
            + ", 카피/선별=" + ("Claude" if self.config.has_anthropic else "mock")
        )

    @property
    def roster(self) -> list[tuple[str, str]]:
        return [(a.name, a.role) for a in (self.discovery, self.curation, self.copy, self.publish)]

    def curate(self, brief: Brief) -> OrchestrationResult:
        """발굴 + 선별까지만 (무료 triage). 카피·딥링크는 생략."""
        result = OrchestrationResult()
        d_log = AgentLog(self.discovery.name)
        products = self.discovery.run(brief, d_log)
        result.logs.append(d_log)

        c_log = AgentLog(self.curation.name)
        result.shortlist = self.curation.run(brief, products, c_log)
        result.logs.append(c_log)
        return result

    def run(self, brief: Brief, save: bool = True) -> OrchestrationResult:
        """발굴→선별→카피→게시준비 전체 사슬."""
        result = self.curate(brief)

        copy_log = AgentLog(self.copy.name)
        pub_log = AgentLog(self.publish.name)
        for scored in result.shortlist:
            captions = self.copy.run(brief, scored, copy_log)
            piece = self.publish.run(brief, scored, captions, pub_log)
            if save:
                self.storage.save_content(piece)
            result.pieces.append(piece)
        result.logs.extend([copy_log, pub_log])
        return result
