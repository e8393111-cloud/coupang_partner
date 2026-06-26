"""파이프라인 오케스트레이션: 발굴 → 카피 → 딥링크 → 저장."""

from __future__ import annotations

import re

from .captions import PLATFORMS, CaptionGenerator
from .config import Config
from .coupang import CoupangClient
from .models import ContentPiece, Product
from .storage import Storage

# 쿠팡 파트너스 광고 고지 (의무 표기)
DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."

_SUBID_SAFE = re.compile(r"[^A-Za-z0-9]")


def _make_subid(prefix: str, platform: str, product: Product) -> str:
    """채널/플랫폼/상품별 성과 분리를 위한 subId. 영숫자만 허용."""
    raw = f"{prefix}-{platform}-{product.product_id}"
    return _SUBID_SAFE.sub("", raw)[:32]


class Pipeline:
    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config.load()
        self.coupang = CoupangClient(
            self.config.coupang_access_key, self.config.coupang_secret_key
        )
        self.captions = CaptionGenerator(
            self.config.anthropic_api_key, self.config.caption_model
        )
        self.storage = Storage(self.config.db_path)

    @property
    def mode_note(self) -> str:
        parts = []
        parts.append("쿠팡=" + ("실 API" if not self.coupang.is_mock else "mock"))
        parts.append("카피=" + ("Claude" if not self.captions.is_mock else "mock"))
        return ", ".join(parts)

    def run(
        self,
        keyword: str | None = None,
        category_id: int | None = None,
        limit: int = 5,
        platforms: tuple[str, ...] = PLATFORMS,
        save: bool = True,
    ) -> list[ContentPiece]:
        """발굴부터 저장까지 한 번에 실행하고 ContentPiece 목록을 반환."""
        products = self._discover(keyword, category_id, limit)
        pieces: list[ContentPiece] = []
        for product in products:
            piece = self.build(product, platforms)
            if save:
                self.storage.save_content(piece)
            pieces.append(piece)
        return pieces

    def _discover(
        self, keyword: str | None, category_id: int | None, limit: int
    ) -> list[Product]:
        if category_id is not None:
            return self.coupang.best_category_products(category_id, limit)
        if keyword:
            return self.coupang.search_products(keyword, limit)
        raise ValueError("keyword 또는 category_id 중 하나는 있어야 합니다.")

    def build(self, product: Product, platforms: tuple[str, ...] = PLATFORMS) -> ContentPiece:
        """상품 1건 → 플랫폼별 카피 + 딥링크가 묶인 콘텐츠 단위 생성."""
        # 플랫폼별로 subId 를 다르게 줘 성과를 분리 추적. 딥링크는 대표 1개로 묶되
        # subId 접두를 상품 단위로 부여한다.
        sub_id = _make_subid(self.config.subid_prefix, "all", product)
        link_map = self.coupang.create_deeplink([product.product_url], sub_id=sub_id)
        deeplink = link_map.get(product.product_url, product.product_url)

        captions = self.captions.generate(product, platforms)
        return ContentPiece(
            product=product, deeplink=deeplink, sub_id=sub_id, captions=captions
        )
