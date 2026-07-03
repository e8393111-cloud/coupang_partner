"""경량 에이전트 베이스.

각 분야 에이전트 = 역할(role) + `run(...)→산출물` 모듈. 지능이 필요한 곳에서만
Claude를 역할별 프롬프트로 호출한다. 자율 도구 루프(Agent SDK)는 쓰지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Brief:
    """오케스트레이터가 에이전트 사슬에 흘려보내는 작업 지시."""

    keyword: str | None = None
    category_id: int | None = None
    niche: str | None = None       # 니치(주제) — keyword 없으면 TrendAgent 가 이걸로 발굴
    platforms: tuple[str, ...] = ("threads", "tiktok")
    target_count: int = 3          # 최종 콘텐츠 개수
    shortlist_size: int = 10       # 발굴·선별 후보 수
    use_vision: bool = False       # 신박도(Claude vision) 점수 사용 여부
    with_media: bool = False       # 미디어 소재 기획서 생성 여부
    market: str = "kr"             # 마켓 키 (kr | global | ali)
    language: str = "ko"           # 카피 언어 (ko | en)
    currency: str = "KRW"          # 가격대 점수용 통화
    audience: str = "general"      # 타깃 (예: "40+")


@dataclass
class AgentLog:
    """에이전트가 '왜 이렇게 했는지' 남기는 추적 기록."""

    agent: str
    messages: list[str] = field(default_factory=list)

    def add(self, msg: str) -> None:
        self.messages.append(msg)


@runtime_checkable
class Agent(Protocol):
    """모든 분야 에이전트가 따르는 최소 규약."""

    name: str
    role: str

    def run(self, *args, **kwargs):  # 산출물은 에이전트마다 다름
        ...
