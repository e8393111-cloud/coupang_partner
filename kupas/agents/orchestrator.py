"""오케스트레이터 — 마켓별로 소스·언어를 선택해 에이전트 사슬을 실행한다.

  DiscoveryAgent ─▶ CurationAgent ─▶ CopyAgent ─▶ MediaAgent(선택) ─▶ PublishAgent

`--market all` 이면 국내+글로벌을 한 번에 돌린다(동시진행).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from ..captions import CaptionGenerator
from ..config import Config
from ..models import ContentPiece, ScoredProduct
from ..sources import MARKETS, get_source, resolve_markets
from ..storage import Storage
from .base import AgentLog, Brief
from .copy import CopyAgent
from .curation import CurationAgent, ScoreWeights
from .discovery import DiscoveryAgent
from .media import MediaAgent
from .publish import PublishAgent


@dataclass
class OrchestrationResult:
    pieces: list[ContentPiece] = field(default_factory=list)
    shortlist: list[ScoredProduct] = field(default_factory=list)
    logs: list[AgentLog] = field(default_factory=list)


class Orchestrator:
    def __init__(self, config: Config | None = None, weights: ScoreWeights | None = None) -> None:
        self.config = config or Config.load()
        self.storage = Storage(self.config.db_path)

        llm = None
        if self.config.has_anthropic:
            import anthropic

            llm = anthropic.Anthropic(api_key=self.config.anthropic_api_key)
        model = self.config.caption_model

        self.discovery = DiscoveryAgent(llm=llm, model=model)
        self.curation = CurationAgent(weights=weights, llm=llm, model=model)
        self.copy = CopyAgent(CaptionGenerator(self.config.anthropic_api_key, model))
        self.media = MediaAgent(llm=llm, model=model)
        self.publish = PublishAgent(self.config.subid_prefix)

    @property
    def mode_note(self) -> str:
        return (
            "쿠팡=" + ("실 API" if self.config.has_coupang else "mock")
            + ", 글로벌=mock, 카피/선별=" + ("Claude" if self.config.has_anthropic else "mock")
        )

    @property
    def roster(self) -> list[tuple[str, str]]:
        agents = (self.discovery, self.curation, self.copy, self.media, self.publish)
        return [(a.name, a.role) for a in agents]

    def _market_brief(self, brief: Brief, market_key: str) -> Brief:
        """마켓에 맞춰 언어·통화를 채운 Brief 사본."""
        m = MARKETS[market_key]
        return replace(brief, market=market_key, language=m.language, currency=m.currency)

    # ------------------------------------------------------------------ #
    # 단일 마켓
    # ------------------------------------------------------------------ #
    def curate(self, brief: Brief) -> OrchestrationResult:
        """발굴 + 선별까지만 (무료 triage)."""
        source = get_source(brief.market, self.config)
        result = OrchestrationResult()
        d_log = AgentLog(self.discovery.name)
        products = self.discovery.run(brief, source, d_log)
        result.logs.append(d_log)

        c_log = AgentLog(self.curation.name)
        result.shortlist = self.curation.run(brief, products, c_log)
        result.logs.append(c_log)
        return result

    def run(self, brief: Brief, save: bool = True) -> OrchestrationResult:
        """발굴→선별→카피→(미디어)→게시준비 전체 사슬 (단일 마켓)."""
        source = get_source(brief.market, self.config)
        result = self.curate(brief)

        copy_log = AgentLog(self.copy.name)
        media_log = AgentLog(self.media.name)
        pub_log = AgentLog(self.publish.name)
        for scored in result.shortlist:
            captions = self.copy.run(brief, scored, copy_log)
            piece = self.publish.run(brief, scored, captions, source, pub_log)
            if brief.with_media:
                piece.media = self.media.run(brief, scored, captions, media_log)
            if save:
                self.storage.save_content(piece)
            result.pieces.append(piece)
        result.logs.append(copy_log)
        if brief.with_media:
            result.logs.append(media_log)
        result.logs.append(pub_log)
        return result

    # ------------------------------------------------------------------ #
    # 멀티 마켓 (국내+글로벌 동시)
    # ------------------------------------------------------------------ #
    def run_markets(self, brief: Brief, save: bool = True) -> OrchestrationResult:
        """brief.market 이 'all' 이면 국내+글로벌을 모두 실행해 합친다."""
        merged = OrchestrationResult()
        for key in resolve_markets(brief.market):
            r = self.run(self._market_brief(brief, key), save=save)
            merged.pieces.extend(r.pieces)
            merged.shortlist.extend(r.shortlist)
            merged.logs.extend(r.logs)
        return merged

    def curate_markets(self, brief: Brief) -> OrchestrationResult:
        merged = OrchestrationResult()
        for key in resolve_markets(brief.market):
            r = self.curate(self._market_brief(brief, key))
            merged.shortlist.extend(r.shortlist)
            merged.logs.extend(r.logs)
        return merged
