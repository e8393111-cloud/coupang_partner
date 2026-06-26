"""파이프라인 전반에서 쓰는 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Product:
    """쿠팡 상품 한 건."""

    product_id: str
    name: str
    price: int
    image_url: str
    product_url: str
    category_name: str = ""
    is_rocket: bool = False

    @classmethod
    def from_coupang(cls, raw: dict[str, Any]) -> "Product":
        return cls(
            product_id=str(raw.get("productId", "")),
            name=raw.get("productName", ""),
            price=int(raw.get("productPrice", 0) or 0),
            image_url=raw.get("productImage", ""),
            product_url=raw.get("productUrl", ""),
            category_name=raw.get("categoryName", ""),
            is_rocket=bool(raw.get("isRocket", False)),
        )


@dataclass
class ProductScore:
    """선별 에이전트가 매긴 상품 점수. 하위 점수 합 + 근거."""

    commission: float = 0.0   # 수수료 기대값 점수
    price: float = 0.0        # 가격대 적합도 점수
    rocket: float = 0.0       # 로켓배송 보너스
    novelty: float = 0.0      # 신박도(비주얼 임팩트) 점수, 선택
    total: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass
class ScoredProduct:
    """상품 + 점수. 선별 에이전트의 산출물."""

    product: "Product"
    score: ProductScore


@dataclass
class Caption:
    """한 플랫폼용으로 생성된 후킹 카피."""

    platform: str            # "threads" | "tiktok"
    hook: str                # 첫 줄 — 스크롤 멈추게 하는 후킹
    body: str                # 본문 (제품 설득)
    hashtags: list[str] = field(default_factory=list)
    alt_hooks: list[str] = field(default_factory=list)  # A/B 테스트용 대체 후킹

    def render(self, link: str, disclosure: str) -> str:
        """게시용 최종 텍스트로 조립한다 (광고 고지 + 링크 포함)."""
        tags = " ".join(f"#{t.lstrip('#')}" for t in self.hashtags)
        return f"{self.hook}\n\n{self.body}\n\n{disclosure}\n{link}\n\n{tags}".strip()


@dataclass
class Shot:
    """영상/캐러셀의 한 컷."""

    seconds: float
    visual: str       # 화면에 보일 장면
    overlay: str      # 화면 자막(텍스트 오버레이)


@dataclass
class MediaBrief:
    """틱톡·릴스·캐러셀 제작용 소재 기획서."""

    platform: str
    format: str                  # 예: "9:16 세로 숏폼 영상"
    duration_sec: float
    shots: list[Shot] = field(default_factory=list)
    music: str = ""              # BGM/페이싱 가이드
    image_prompts: list[str] = field(default_factory=list)  # 이미지 생성 프롬프트
    video_prompt: str = ""       # 영상 생성 프롬프트


@dataclass
class ContentPiece:
    """상품 + 플랫폼별 카피 + 딥링크가 묶인 최종 콘텐츠 단위."""

    product: Product
    deeplink: str
    sub_id: str
    captions: list[Caption] = field(default_factory=list)
    score: ProductScore | None = None
    media: list[MediaBrief] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "product": asdict(self.product),
            "deeplink": self.deeplink,
            "sub_id": self.sub_id,
            "captions": [asdict(c) for c in self.captions],
            "score": asdict(self.score) if self.score else None,
            "media": [asdict(m) for m in self.media],
        }
