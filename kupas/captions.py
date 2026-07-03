"""Claude 로 스레드/틱톡용 후킹 카피를 생성한다.

실제로 터진 게시물 패턴(`exemplars.py`)을 few-shot 으로 주입해 후킹 강도를 높이고,
A/B 테스트용 대체 후킹까지 함께 뽑는다.

ANTHROPIC_API_KEY 가 없으면 후킹 아키타입 기반 mock 카피로 대체한다.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .exemplars import archetype_for, fewshot_block
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
    "reels": (
        "인스타 릴스용. 첫 줄은 강한 후킹, 본문은 담백한 후기 말투. 40+도 편하게 읽히게."
    ),
    "shorts": (
        "유튜브 쇼츠용. 첫 줄은 3초 후킹, 본문은 혜택을 명확히. 차분하고 신뢰가는 톤."
    ),
}

# 영어(글로벌) 플랫폼 가이드
_PLATFORM_GUIDE_EN = {
    "reels": "Instagram Reels caption. Strong first-line hook, then a calm, benefit-led review tone that reads easily for a 40+ audience.",
    "shorts": "YouTube Shorts caption. 3-second hook first, then clear benefits. Calm, trustworthy tone.",
    "tiktok": "TikTok caption. Punchy 3-second hook, short rhythmic lines.",
    "threads": "Threads post. Curiosity/awe hook, 2-4 line natural review voice.",
}

_SYSTEM = (
    "너는 한국 쿠팡 파트너스 숏폼 마케터다. 신박한 제품을 소개해 클릭을 유도하는 "
    "후킹 카피를 쓴다. 규칙: (1) 과장 광고/허위 효능 표현 금지, 사실 기반으로 흥미만 "
    "극대화. (2) 첫 줄 hook 은 스크롤을 멈추게 하는 게 최우선. 예시의 '구조'를 참고하되 "
    "문장은 상품에 맞게 새로 써라(복붙 금지). (3) 해시태그는 검색·노출에 실제 도움이 "
    "되는 5~8개. (4) 광고 고지 문구와 링크는 카피 본문에 넣지 마라(시스템이 따로 붙인다). "
    "(5) alt_hooks 에는 서로 다른 심리 트리거의 대체 첫 줄 2개를 제시해 A/B 테스트가 "
    "가능하게 하라."
)

_SYSTEM_EN = (
    "You are a global affiliate short-form marketer targeting buyers aged 40+. "
    "Write scroll-stopping hook captions. Rules: (1) No exaggerated or false claims — "
    "maximize interest with facts only. (2) The first-line hook matters most; borrow the "
    "STRUCTURE of the examples but write fresh sentences for this product (no copying). "
    "(3) 5-8 useful hashtags. (4) Do NOT put the affiliate disclosure or link in the body "
    "(the system appends them). (5) alt_hooks: two alternative first lines using different "
    "psychological triggers for A/B testing. Keep the tone clear and benefit-led for 40+."
)


def _system_for(language: str) -> str:
    return _SYSTEM_EN if language == "en" else _SYSTEM


def _guide_for(platform: str, language: str) -> str:
    if language == "en":
        return _PLATFORM_GUIDE_EN.get(platform, _PLATFORM_GUIDE_EN["tiktok"])
    return _PLATFORM_GUIDE.get(platform, _PLATFORM_GUIDE["tiktok"])


class _CaptionOut(BaseModel):
    hook: str = Field(description="스크롤을 멈추게 하는 가장 강한 첫 줄")
    alt_hooks: list[str] = Field(description="서로 다른 트리거의 대체 첫 줄 2개")
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

    def generate(
        self, product: Product, platforms: tuple[str, ...] = PLATFORMS, language: str = "ko"
    ) -> list[Caption]:
        return [self._one(product, p, language) for p in platforms]

    def _one(self, product: Product, platform: str, language: str = "ko") -> Caption:
        if self._client is None:
            return _mock_caption(product, platform, language)

        guide = _guide_for(platform, language)
        price = _fmt_price(product.price, language)
        if language == "en":
            prompt = (
                f"{guide}\n\n{fewshot_block(platform, 'en')}\n\n"
                f"[Product]\n- Name: {product.name}\n- Price: {price}\n"
                f"- Category: {product.category_name}\n\n"
                f"Write a {platform} caption for this product, borrowing the hook structure "
                f"from the examples with fresh sentences."
            )
        else:
            prompt = (
                f"{guide}\n\n{fewshot_block(platform, 'ko')}\n\n"
                f"[상품 정보]\n- 이름: {product.name}\n- 가격: {price}\n"
                f"- 카테고리: {product.category_name}\n"
                f"- 로켓배송: {'예' if product.is_rocket else '아니오'}\n\n"
                f"이 상품으로 {platform} 게시물 카피를 만들어줘. 예시의 후킹 구조를 참고해 "
                f"이 상품에 맞는 새 문장으로."
            )
        resp = self._client.messages.parse(
            model=self.model,
            max_tokens=2000,
            thinking={"type": "adaptive"},
            system=_system_for(language),
            messages=[{"role": "user", "content": prompt}],
            output_format=_CaptionOut,
        )
        out = resp.parsed_output
        if out is None:  # 안전장치 (거부 등)
            return _mock_caption(product, platform, language)
        return Caption(
            platform=platform,
            hook=out.hook,
            body=out.body,
            hashtags=[h.lstrip("#") for h in out.hashtags],
            alt_hooks=list(out.alt_hooks),
        )


def _fmt_price(price: int, language: str) -> str:
    return f"${price}" if language == "en" else f"{price:,}원"


def _mock_caption(product: Product, platform: str, language: str = "ko") -> Caption:
    """Claude 없이도 아키타입을 돌려가며 다양한 후킹을 만든다 (언어별)."""
    seed = abs(hash(product.product_id + platform))
    primary = archetype_for(seed, language)
    alt1 = archetype_for(seed + 1, language)
    alt2 = archetype_for(seed + 2, language)
    price = _fmt_price(product.price, language)
    if language == "en":
        cat = product.category_name or "must-have"
        body = f"{price}? For this? A little {cat} upgrade that just works. Saved it instantly."
        tags = [cat.lower(), "amazonfinds", "musthave", "tiktokmademebuyit", "40plus", "homegadgets"]
    else:
        cat = product.category_name or "추천템"
        body = f"{price}에 이게 된다고?\n{cat} 바꾸는 신박템. 처음 보고 바로 저장함."
        tags = [cat, "쿠팡추천", product.name.split()[0], "꿀템", "추천템", "갓성비"]
    return Caption(
        platform=platform,
        hook=f"{primary.template} {product.name}",
        body=body,
        hashtags=tags,
        alt_hooks=[alt1.template, alt2.template],
    )
