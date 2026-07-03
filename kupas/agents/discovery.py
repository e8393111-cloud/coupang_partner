"""발굴 에이전트 — 후보 상품을 찾아온다.

쿠팡 상품검색/베스트카테고리를 도구로 쓰고, Claude가 있으면 시드 키워드를
연관 키워드로 확장해 후보 폭을 넓힌다(선택).
"""

from __future__ import annotations

import math

from ..coupang import CoupangClient
from ..models import Product
from .base import AgentLog, Brief


class DiscoveryAgent:
    name = "discovery"
    role = "트렌드 후보 발굴가 — 임팩트 있는 상품 후보를 모은다"

    def __init__(self, coupang: CoupangClient, llm=None, model: str = "claude-opus-4-8") -> None:
        self.coupang = coupang
        self.llm = llm
        self.model = model

    def run(self, brief: Brief, log: AgentLog) -> list[Product]:
        if brief.category_id is not None:
            products = self.coupang.best_category_products(brief.category_id, brief.shortlist_size)
            log.add(f"카테고리 {brief.category_id} 베스트 {len(products)}개 발굴")
            return products

        if not brief.keyword:
            raise ValueError("keyword 또는 category_id 중 하나는 있어야 합니다.")

        keywords = self._expand(brief.keyword, log)
        seen: dict[str, Product] = {}
        # 올림 나눗셈 — 여러 키워드로 나눠도 shortlist_size 아래로 부족해지지 않게
        per_kw = max(1, math.ceil(brief.shortlist_size / len(keywords)))
        for kw in keywords:
            for p in self.coupang.search_products(kw, per_kw):
                seen.setdefault(p.product_id, p)
        products = list(seen.values())[: brief.shortlist_size]
        log.add(f"키워드 {keywords} → 중복제거 {len(products)}개 발굴")
        return products

    def _expand(self, keyword: str, log: AgentLog) -> list[str]:
        """Claude 가 있으면 연관 키워드로 확장, 없으면 원 키워드만."""
        if self.llm is None:
            return [keyword]
        try:
            resp = self.llm.messages.create(
                model=self.model,
                max_tokens=200,
                system="쿠팡에서 잘 팔릴 만한 연관 검색 키워드를 제안하는 도우미. "
                "쉼표로 구분한 키워드만 출력.",
                messages=[{
                    "role": "user",
                    "content": f"'{keyword}' 와 관련해 숏폼에서 터질 만한 검색 키워드 3개를 "
                    f"쉼표로만 답해줘. 원 키워드 포함.",
                }],
            )
            text = next((b.text for b in resp.content if b.type == "text"), keyword)
            kws = [k.strip() for k in text.split(",") if k.strip()][:4]
            if keyword not in kws:
                kws.insert(0, keyword)
            log.add(f"키워드 확장: {kws}")
            return kws
        except Exception as e:  # 확장 실패해도 발굴은 계속
            log.add(f"키워드 확장 실패({e}), 원 키워드 사용")
            return [keyword]
