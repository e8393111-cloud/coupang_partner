"""검증된 후킹 패턴과 예시 게시물.

실제 쿠파스 숏폼에서 잘 터진 게시물의 '첫 줄' 구조를 아키타입으로 정리해
카피 생성 시 few-shot 으로 모델에 주입한다. mock 카피의 다양화에도 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HookArchetype:
    name: str
    template: str        # 후킹 골격 ({product} 치환 가능)
    why: str             # 왜 먹히는지


# 잘 터진 첫 줄의 심리 트리거별 아키타입
HOOK_ARCHETYPES: list[HookArchetype] = [
    HookArchetype("충격·호기심", "이거 보고 눈을 의심했다…", "스크롤을 멈추게 하는 즉각적 의문 유발"),
    HookArchetype("제보·발견", "이거 만든 사람 상 줘야 하는 거 아니냐?", "발견의 흥분 + 공유 욕구 자극"),
    HookArchetype("후회·경고", "이걸 이제야 알았다니… 그동안 손해 본 게 얼만지", "FOMO·후회 회피 심리"),
    HookArchetype("가격 충격", "이 가격에 이게 된다고?", "가성비 의심 → 확인 욕구"),
    HookArchetype("불편 해결", "그동안 받던 스트레스, 이걸로 한 방에 끝났다", "구체적 페인포인트 공감"),
    HookArchetype("비포·애프터", "사기 전 vs 산 후, 이렇게 달라질 줄", "변화의 대비로 설득"),
]


# 영어(글로벌 40+) 후킹 아키타입 — 혜택·명확 중심
HOOK_ARCHETYPES_EN: list[HookArchetype] = [
    HookArchetype("shock", "I couldn't believe this actually exists…", "즉각적 호기심"),
    HookArchetype("regret", "Why did no one tell me about this sooner?", "후회·FOMO"),
    HookArchetype("relief", "The one thing my back needed all along", "구체적 페인포인트"),
    HookArchetype("value", "This costs less than a dinner out?", "가성비 충격"),
    HookArchetype("routine", "This quietly changed my whole day", "일상 개선(40+ 공감)"),
    HookArchetype("before_after", "Before vs after — I wasn't ready for this", "변화 대비"),
]


@dataclass(frozen=True)
class Exemplar:
    platform: str
    product: str
    hook: str
    body: str


# few-shot 예시 게시물 (실제로 터진 패턴 기반)
EXEMPLARS: list[Exemplar] = [
    Exemplar(
        platform="threads",
        product="바닥에 안 닿는 야전침대 텐트",
        hook="이거 만든 사람 상 줘야 하는 거 아니냐?",
        body="텐트가 바닥에 안 닿는다니… 비 온 뒤 젖은 땅, 벌레, 흙먼지까지 신경 안 써도 되다니. "
        "처음 보고 눈을 의심했다. 이건 캠핑계의 혁명인데.",
    ),
    Exemplar(
        platform="threads",
        product="무선 핸디 가습 선풍기",
        hook="여름에 이거 없이 어떻게 버텼지",
        body="손에 들고 다니는데 미스트까지 나온다. 카페·지하철·산책 어디서든 시원하고 촉촉. "
        "충전 한 번에 하루 종일 가는 게 반칙.",
    ),
    Exemplar(
        platform="tiktok",
        product="초강력 차량용 무선 청소기",
        hook="차 안 먼지 이걸로 5초컷",
        body="시트 틈새 과자 부스러기까지 쪽쪽. 무선이라 선 꼬일 일 없고 흡입력은 유선급. "
        "한 번 쓰면 세차장 안 감.",
    ),
    Exemplar(
        platform="tiktok",
        product="각도조절 노트북 거치대",
        hook="목 디스크 올 뻔한 거 이걸로 살았다",
        body="화면이 눈높이로 딱. 접으면 가방에 쏙. 카페 작업러 필수템인데 왜 이제 샀지.",
    ),
]


# 영어 few-shot 예시 (글로벌 40+)
EXEMPLARS_EN: list[Exemplar] = [
    Exemplar(
        platform="reels",
        product="Cordless Neck & Shoulder Massager",
        hook="Why did no one tell me about this sooner?",
        body="Deep-tissue relief in 10 minutes, cordless, right at your desk. "
        "My shoulders haven't felt this loose in years.",
    ),
    Exemplar(
        platform="shorts",
        product="Anti-Fatigue Kitchen Standing Mat",
        hook="The one thing my kitchen was missing",
        body="Stand for an hour and your back still feels fine. "
        "Wish I'd bought this a decade ago.",
    ),
    Exemplar(
        platform="tiktok",
        product="Raised Garden Bed Planter Kit",
        hook="No more bending over to garden",
        body="Waist-high beds, zero back strain, set up in minutes. "
        "Gardening just got easy again.",
    ),
]


def fewshot_block(platform: str, language: str = "ko", limit: int = 2) -> str:
    """플랫폼·언어에 맞는 few-shot 예시를 프롬프트용 텍스트로 만든다."""
    pool = EXEMPLARS_EN if language == "en" else EXEMPLARS
    picks = [e for e in pool if e.platform == platform][:limit]
    if not picks:
        picks = pool[:limit]
    header = "[High-performing examples]" if language == "en" else "[잘 터진 예시]"
    lines = [header]
    for e in picks:
        lines.append(f"- product: {e.product}\n  hook: {e.hook}\n  body: {e.body}")
    return "\n".join(lines)


def archetype_for(seed: int, language: str = "ko") -> HookArchetype:
    """시드로 아키타입을 고르게 분산 선택 — mock 다양화용 (언어별)."""
    pool = HOOK_ARCHETYPES_EN if language == "en" else HOOK_ARCHETYPES
    return pool[seed % len(pool)]
