"""Claude 로 스레드/틱톡용 후킹 카피를 생성한다.

스크린샷의 `todaypick100` 게시물 패턴(호기심·감탄 유발 첫 줄 → 제품 설득 →
광고 고지 + 링크)을 모델에게 학습시켜, 상품 하나당 플랫폼별 카피를 뽑는다.

ANTHROPIC_API_KEY 가 없으면 템플릿 기반 mock 카피로 대체한다.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .models import Caption, Product

PLATFORMS = ("threads", "tiktok")

# 플랫폼별 톤/형식 가이드
_PLATFORM_GUIDE = {
    "threads": (
        "스레드(Threads)용. 텍스트+이미지 중심. 첫 줄(hook)은 호기심이나 감탄을 "
        "강하게 자극해 스크롤을 멈추게 한다. 본문은 2~4줄, 제품의 '이게 된다고?' 포인트를 "
        "구체적으로. 과한 이모지 금지, 자연스러운 후기 말투."
    ),
    "tiktok": (
        "틱톡 영상 캡션용. 첫 줄(hook)은 영상 초반 3초에 띄울 짧고 강한 한 줄. "
        "본문은 영상에서 보여줄 포인트를 짧게. 트렌디한 구어체, 줄 사이 리듬감 있게."
    ),
}

_SYSTEM = (
    "너는 한국 쿠팡 파트너스 숏폼 마케터다. 신박한 제품을 소개해 클릭을 유도하는 "
    "후킹 카피를 쓴다. 규칙: (1) 과장 광고/허위 효능 표현 금지, 사실 기반으로 흥미만 "
    "극대화. (2) 첫 줄 hook 은 스크롤을 멈추게 하는 게 최우선. (3) 해시태그는 검색·노출에 "
    "실제 도움이 되는 것 5~8개. (4) 광고 고지 문구와 링크는 카피 본문에 넣지 마라(시스템이 "
    "따로 붙인다)."
)


class _CaptionOut(BaseModel):
    hook: str = Field(description="스크롤을 멈추게 하는 강렬한 첫 줄")
    body: str = Field(description="제품을 설득하는 본문 2~4줄")
    hashtags: list[str] = Field(description="해시태그 5~8개, # 제외한 단어만")


class CaptionGenerator:
    def __init__(self, api_key: str | None = None, model: str = "claude-opus-4-8") -> None:
        self.model = model
        self._client = None
        if api_key:
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key)

    @property
    def is_mock(self) -> bool:
        return self._client is None

    def generate(self, product: Product, platforms: tuple[str, ...] = PLATFORMS) -> list[Caption]:
        return [self._one(product, p) for p in platforms]

    def _one(self, product: Product, platform: str) -> Caption:
        if self._client is None:
            return _mock_caption(product, platform)

        guide = _PLATFORM_GUIDE.get(platform, "")
        prompt = (
            f"{guide}\n\n"
            f"[상품 정보]\n"
            f"- 이름: {product.name}\n"
            f"- 가격: {product.price:,}원\n"
            f"- 카테고리: {product.category_name}\n"
            f"- 로켓배송: {'예' if product.is_rocket else '아니오'}\n\n"
            f"이 상품으로 {platform} 게시물 카피를 만들어줘."
        )
        resp = self._client.messages.parse(
            model=self.model,
            max_tokens=2000,
            thinking={"type": "adaptive"},
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=_CaptionOut,
        )
        out = resp.parsed_output
        if out is None:  # 안전장치 (거부 등)
            return _mock_caption(product, platform)
        return Caption(
            platform=platform,
            hook=out.hook,
            body=out.body,
            hashtags=[h.lstrip("#") for h in out.hashtags],
        )


def _mock_caption(product: Product, platform: str) -> Caption:
    cat = product.category_name or "추천템"
    return Caption(
        platform=platform,
        hook=f"이거 보고 눈을 의심했다… {product.name}",
        body=(
            f"{product.price:,}원에 이게 된다고?\n"
            f"{cat} 바꾸는 신박템. 처음 보고 바로 저장함."
        ),
        hashtags=[cat, "쿠팡추천", product.name.split()[0], "꿀템", "추천템", "갓성비"],
    )
