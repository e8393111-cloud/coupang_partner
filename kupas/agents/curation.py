"""선별 에이전트 (★1순위) — 터질 상품만 골라낸다.

2단계 깔때기:
  1) 휴리스틱 점수: 수수료 기대값 · 가격대 적합도 · 로켓 (전수, 무료)
  2) 신박도 점수: 상품명+이미지로 호기심 유발도 (shortlist만, Claude vision, 선택)
점수로 랭킹해 상위 target_count 개만 다음 단계로 넘긴다.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

from ..models import Product, ProductScore, ScoredProduct
from .base import AgentLog, Brief

# 카테고리별 수수료율(추정). 실제 정산율과 다를 수 있으니 운영하며 조정.
# 미지정 카테고리는 DEFAULT_COMMISSION 적용.
CATEGORY_COMMISSION: dict[str, float] = {
    "가전디지털": 0.03,
    "생활가전": 0.03,
    "주방용품": 0.035,
    "캠핑": 0.035,
    "자동차용품": 0.035,
    "사무용품": 0.03,
    "패션": 0.04,
    "뷰티": 0.04,
}
DEFAULT_COMMISSION = 0.03

# 가격대 sweet-spot: 통화별. 이 근처에서 점수 최고, 너무 싸거나 비싸면 감점.
SWEET_SPOT = {"KRW": 50_000, "USD": 40}
SIGMA = {"KRW": 80_000, "USD": 70}

# 40+ 타깃이 잘 사는 카테고리 (국내/영문) — 가점
AUDIENCE_40_CATS = {
    "건강", "생활가전", "주방용품", "정원", "반려", "안마",
    "health", "kitchen", "home", "garden", "pet", "auto",
}


@dataclass
class ScoreWeights:
    """점수 가중치. 운영하며 튜닝."""

    commission: float = 1.0
    price: float = 1.0
    rocket: float = 1.0
    novelty: float = 1.5  # 신박함이 숏폼에선 가장 중요


def commission_rate(category: str) -> float:
    return CATEGORY_COMMISSION.get(category, DEFAULT_COMMISSION)


def _commission_score(product: Product) -> tuple[float, str]:
    """수수료 기대값(원)을 0~100 으로 환산. 3만원 기대수수료를 만점 근처로."""
    expected = product.price * commission_rate(product.category_name)
    score = min(100.0, expected / 30_000 * 100)
    return score, f"기대수수료 ~{int(expected):,}원"


def _price_score(product: Product, currency: str = "KRW") -> tuple[float, str]:
    """통화별 sweet-spot 가우시안 곡선."""
    center = SWEET_SPOT.get(currency, SWEET_SPOT["KRW"])
    sigma = SIGMA.get(currency, SIGMA["KRW"])
    diff = product.price - center
    score = 100.0 * math.exp(-(diff**2) / (2 * sigma**2))
    return score, f"가격대 적합도 {int(score)}"


def _rocket_score(product: Product) -> tuple[float, str]:
    return (100.0, "로켓배송") if product.is_rocket else (0.0, "일반배송")


class CurationAgent:
    name = "curation"
    role = "상품 큐레이터 — 수수료·가격대·로켓·신박함으로 터질 상품을 선별"

    def __init__(
        self,
        weights: ScoreWeights | None = None,
        llm=None,
        model: str = "claude-opus-4-8",
    ) -> None:
        self.weights = weights or ScoreWeights()
        self.llm = llm
        self.model = model

    def run(
        self,
        brief: Brief,
        products: list[Product],
        log: AgentLog,
        boosts: dict[str, float] | None = None,
    ) -> list[ScoredProduct]:
        # 1단계: 전수 휴리스틱 점수 (통화·타깃·성과학습 반영)
        scored = [
            ScoredProduct(p, self._heuristic(p, brief.currency, brief.audience, boosts))
            for p in products
        ]
        scored.sort(key=lambda s: s.score.total, reverse=True)
        log.add(f"휴리스틱 점수 {len(scored)}개 산출")

        # 2단계: shortlist 에만 신박도(비전) 점수 — 선택
        shortlist = scored[: brief.shortlist_size]
        if brief.use_vision:
            self._apply_novelty(shortlist, log)
            shortlist.sort(key=lambda s: s.score.total, reverse=True)

        final = shortlist[: brief.target_count]
        log.add(
            "선별 완료: "
            + ", ".join(f"{s.product.name}({int(s.score.total)})" for s in final)
        )
        return final

    # ------------------------------------------------------------------ #
    def _heuristic(
        self,
        product: Product,
        currency: str = "KRW",
        audience: str = "general",
        boosts: dict[str, float] | None = None,
    ) -> ProductScore:
        w = self.weights
        c_s, c_r = _commission_score(product)
        p_s, p_r = _price_score(product, currency)
        r_s, r_r = _rocket_score(product)
        total = c_s * w.commission + p_s * w.price + r_s * w.rocket
        reasons = [c_r, p_r, r_r]
        cat = product.category_name.lower()
        # 40+ 타깃이면 해당 카테고리에 가점
        if audience == "40+" and cat in AUDIENCE_40_CATS:
            total += 40.0
            reasons.append("40+ 적합 카테고리 +40")
        # 성과 학습 부스트 (InsightAgent — 실제로 수익 난 카테고리)
        if boosts and cat in boosts:
            total += boosts[cat]
            reasons.append(f"성과 학습 +{boosts[cat]:g}")
        return ProductScore(
            commission=c_s, price=p_s, rocket=r_s, novelty=0.0,
            total=total, reasons=reasons,
        )

    def _apply_novelty(self, shortlist: list[ScoredProduct], log: AgentLog) -> None:
        ratings = self._rate_novelty([s.product for s in shortlist], log)
        for s in shortlist:
            n = float(ratings.get(s.product.product_id, 0))
            s.score.novelty = n
            s.score.total += n * self.weights.novelty
            s.score.reasons.append(f"신박도 {int(n)}")

    def _rate_novelty(self, products: list[Product], log: AgentLog) -> dict[str, float]:
        """Claude vision 으로 '이게 된다고?' 호기심 유발도 0~100 평가."""
        if self.llm is None:
            # mock: 이름 길이/로켓 기반의 가벼운 대체값
            log.add("신박도=mock(휴리스틱 대체)")
            return {p.product_id: float(min(100, 40 + len(p.name) % 50)) for p in products}

        content: list[dict] = [{
            "type": "text",
            "text": "각 상품의 '이게 된다고?' 호기심·감탄 유발도를 0~100으로 평가해줘. "
            "비주얼 임팩트가 클수록 높게. JSON 객체로만 답해: {product_id: 점수}.\n\n"
            + "\n".join(f"- {p.product_id}: {p.name}" for p in products),
        }]
        for p in products:
            if p.image_url:
                content.append({
                    "type": "image",
                    "source": {"type": "url", "url": p.image_url},
                })
        try:
            resp = self.llm.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": content}],
            )
            text = next((b.text for b in resp.content if b.type == "text"), "{}")
            data = json.loads(text[text.find("{") : text.rfind("}") + 1] or "{}")
            log.add(f"신박도 평가 {len(data)}개")
            return {str(k): float(v) for k, v in data.items()}
        except Exception as e:
            log.add(f"신박도 평가 실패({e}), 0점 처리")
            return {}
