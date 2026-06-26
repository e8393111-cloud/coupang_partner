"""카피 에이전트 — 선별된 상품에 플랫폼별 후킹 카피를 붙인다.

기존 CaptionGenerator(Claude 구조화 출력)를 도구로 재사용한다.
"""

from __future__ import annotations

from ..captions import CaptionGenerator
from ..models import Caption, ScoredProduct
from .base import AgentLog, Brief


class CopyAgent:
    name = "copy"
    role = "숏폼 카피라이터 — 스크롤을 멈추게 하는 후킹 카피 작성"

    def __init__(self, generator: CaptionGenerator) -> None:
        self.generator = generator

    def run(self, brief: Brief, scored: ScoredProduct, log: AgentLog) -> list[Caption]:
        caps = self.generator.generate(scored.product, brief.platforms)
        engine = "mock" if self.generator.is_mock else "Claude"
        log.add(f"[{scored.product.name}] {engine} 카피 {len(caps)}종 생성")
        return caps
