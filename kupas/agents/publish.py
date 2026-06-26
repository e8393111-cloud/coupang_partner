"""게시 에이전트 — 딥링크·광고고지를 붙여 게시 직전 콘텐츠로 조립하고 저장한다.

자동 게시는 플랫폼 약관상 포함하지 않는다. 게시 직전(딥링크+카피+고지)까지 책임진다.
"""

from __future__ import annotations

import re

from ..coupang import CoupangClient
from ..models import Caption, ContentPiece, Product, ScoredProduct
from .base import AgentLog, Brief

# 쿠팡 파트너스 광고 고지 (의무 표기)
DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."

_SUBID_SAFE = re.compile(r"[^A-Za-z0-9]")


def make_subid(prefix: str, product: Product) -> str:
    """상품별 성과 분리를 위한 subId. 영숫자만 허용."""
    return _SUBID_SAFE.sub("", f"{prefix}-{product.product_id}")[:32]


class PublishAgent:
    name = "publish"
    role = "게시 준비 담당 — 딥링크·광고고지 조립 및 저장"

    def __init__(self, coupang: CoupangClient, subid_prefix: str = "kupas") -> None:
        self.coupang = coupang
        self.subid_prefix = subid_prefix

    def run(
        self,
        brief: Brief,
        scored: ScoredProduct,
        captions: list[Caption],
        log: AgentLog,
    ) -> ContentPiece:
        product = scored.product
        sub_id = make_subid(self.subid_prefix, product)
        link_map = self.coupang.create_deeplink([product.product_url], sub_id=sub_id)
        deeplink = link_map.get(product.product_url, product.product_url)
        log.add(f"[{product.name}] 딥링크 생성 (subId={sub_id})")
        return ContentPiece(
            product=product,
            deeplink=deeplink,
            sub_id=sub_id,
            captions=captions,
            score=scored.score,
        )
