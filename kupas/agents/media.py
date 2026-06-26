"""미디어 에이전트 — 틱톡·릴스·캐러셀 소재 기획서를 만든다.

카피(후킹)와 상품을 받아 샷리스트(장면+자막)·BGM 가이드·이미지/영상 생성
프롬프트를 산출한다. 실제 영상 생성(외부 유료 API)은 하지 않고, 그 직전 단계인
'무엇을 어떻게 찍을지/생성할지'를 만든다. 생성 연동은 별도 옵션으로 확장 가능.

ANTHROPIC_API_KEY 가 없으면 템플릿 기반 mock 기획서로 대체한다.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..models import Caption, MediaBrief, Product, ScoredProduct, Shot
from .base import AgentLog, Brief

# 플랫폼 → 영상/이미지 포맷
_FORMAT = {
    "tiktok": "9:16 세로 숏폼 영상 (15~30초)",
    "threads": "9:16 또는 4:5 이미지 캐러셀 (2~4장)",
}


class _ShotOut(BaseModel):
    seconds: float = Field(description="이 컷의 길이(초). 이미지 캐러셀이면 슬라이드당 0")
    visual: str = Field(description="화면에 보일 장면")
    overlay: str = Field(description="화면 자막")


class _MediaOut(BaseModel):
    shots: list[_ShotOut] = Field(description="3~6컷의 샷리스트, 첫 컷은 후킹")
    music: str = Field(description="BGM 분위기/페이싱 가이드 한 줄")
    image_prompts: list[str] = Field(description="썸네일·슬라이드용 이미지 생성 프롬프트 1~3개")
    video_prompt: str = Field(description="영상 생성용 프롬프트 한 단락")


class MediaAgent:
    name = "media"
    role = "숏폼 PD — 샷리스트·자막·이미지/영상 생성 프롬프트 기획"

    def __init__(self, llm=None, model: str = "claude-opus-4-8") -> None:
        self.llm = llm
        self.model = model

    @property
    def is_mock(self) -> bool:
        return self.llm is None

    def run(self, brief: Brief, scored: ScoredProduct, captions: list[Caption], log: AgentLog) -> list[MediaBrief]:
        briefs: list[MediaBrief] = []
        for cap in captions:
            briefs.append(self._one(scored.product, cap, log))
        return briefs

    def _one(self, product: Product, caption: Caption, log: AgentLog) -> MediaBrief:
        fmt = _FORMAT.get(caption.platform, _FORMAT["tiktok"])
        if self.llm is None:
            log.add(f"[{product.name}/{caption.platform}] mock 기획서")
            return _mock_brief(product, caption, fmt)

        system = (
            "너는 쿠팡 파트너스 숏폼 PD다. 주어진 후킹 카피로 시선을 잡는 영상/캐러셀을 "
            "기획한다. 첫 컷은 3초 내 후킹이 보여야 한다. 자막은 짧고 굵게. 이미지/영상 "
            "생성 프롬프트는 영문으로, 제품과 분위기가 드러나게 구체적으로 써라."
        )
        prompt = (
            f"플랫폼: {caption.platform} ({fmt})\n"
            f"상품: {product.name} / {product.price:,}원 / {product.category_name}\n"
            f"후킹: {caption.hook}\n본문: {caption.body}\n\n"
            "이 카피를 살리는 소재 기획서를 만들어줘."
        )
        try:
            resp = self.llm.messages.parse(
                model=self.model,
                max_tokens=2000,
                thinking={"type": "adaptive"},
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=_MediaOut,
            )
            out = resp.parsed_output
            if out is None:
                return _mock_brief(product, caption, fmt)
            shots = [Shot(s.seconds, s.visual, s.overlay) for s in out.shots]
            duration = sum(s.seconds for s in shots) or 20.0
            log.add(f"[{product.name}/{caption.platform}] 샷 {len(shots)}컷 기획")
            return MediaBrief(
                platform=caption.platform,
                format=fmt,
                duration_sec=duration,
                shots=shots,
                music=out.music,
                image_prompts=list(out.image_prompts),
                video_prompt=out.video_prompt,
            )
        except Exception as e:
            log.add(f"[{product.name}/{caption.platform}] 기획 실패({e}), mock 대체")
            return _mock_brief(product, caption, fmt)


def _mock_brief(product: Product, caption: Caption, fmt: str) -> MediaBrief:
    cat = product.category_name or "추천템"
    shots = [
        Shot(3.0, f"{product.name} 클로즈업, 손으로 집어드는 장면", caption.hook),
        Shot(5.0, "제품의 핵심 기능을 실제로 써보는 장면", "이게 된다고?"),
        Shot(4.0, "사용 전/후 비교 또는 반응 샷", f"{product.price:,}원 실화?"),
        Shot(3.0, "제품 + 쿠팡 화면, 링크 안내", "프로필 링크 👆"),
    ]
    return MediaBrief(
        platform=caption.platform,
        format=fmt,
        duration_sec=sum(s.seconds for s in shots),
        shots=shots,
        music="트렌디한 비트, 후킹 자막에 맞춰 비트 드롭",
        image_prompts=[
            f"Vertical product hero shot of {product.name}, clean studio lighting, "
            f"Korean shortform thumbnail style, bold text space on top",
            f"Lifestyle scene using {product.name} in everyday {cat} context, bright, eye-catching",
        ],
        video_prompt=(
            f"15-second vertical 9:16 product video for {product.name}. "
            f"Open with a 3-second hook close-up, show the key feature in action, "
            f"end with a call-to-action frame. Energetic, trendy, Korean shortform style."
        ),
    )
