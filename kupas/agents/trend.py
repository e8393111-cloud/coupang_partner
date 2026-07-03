"""트렌드 에이전트 — "뭘 검색할지"를 스스로 정한다.

키워드는 파이프라인에서 유일하게 사람이 매번 생각해내야 했던 입력이다.
니치·시즌(월)·타깃(audience)·마켓(언어)을 조합해 검색 키워드 후보를 뽑아
Discovery 앞에 붙인다. keyword 없이 `run` 을 실행해도 사슬이 돌게 만든다.

Claude 가 있으면 시즌·트렌드를 반영해 생성하고, 없으면 니치·시즌 시드 테이블을
날짜 기반으로 로테이션해 매일 다른 후보를 낸다(다작 운영용).
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from .base import AgentLog, Brief

# ── mock 시드 테이블 ────────────────────────────────────────────────
# 니치 → 키워드 풀. 40+ 페인포인트(건강·편의) 중심.
_POOL_KO: dict[str, list[str]] = {
    "건강": ["목 어깨 마사지기", "발 마사지기", "저주파 안마기", "자세교정 밴드", "혈압계"],
    "주방": ["식기건조대", "주방 발매트", "야채 다지기", "에어프라이어 종이", "실리콘 뚜껑"],
    "홈": ["무선 청소기", "빨래 건조대", "리클라이너 쿠션", "LED 센서등", "가습기"],
    "정원": ["베란다 텃밭 세트", "자동 급수기", "원예 도구 세트", "화분 선반"],
    "반려": ["펫 급수기", "셀프 그루밍 브러시", "펫 계단", "자동 급식기"],
    "여행": ["여행용 압축팩", "목베개", "휴대용 저울", "멀티 어댑터"],
}
_POOL_EN: dict[str, list[str]] = {
    "health": ["neck shoulder massager", "foot massager", "posture corrector", "blood pressure monitor"],
    "kitchen": ["anti fatigue kitchen mat", "vegetable chopper", "dish drying rack", "jar opener"],
    "home": ["cordless vacuum", "reading pillow", "motion sensor light", "humidifier"],
    "garden": ["raised garden bed", "self watering planter", "garden kneeler", "hose reel"],
    "pet": ["pet water fountain", "self grooming brush", "pet stairs", "automatic feeder"],
    "travel": ["packing cubes", "travel pillow", "luggage scale", "universal adapter"],
}

# 월 → 시즌 보정 키워드
_SEASON_KO = {
    12: "방한", 1: "방한", 2: "방한",
    3: "봄나들이", 4: "봄나들이", 5: "캠핑",
    6: "쿨링", 7: "쿨링", 8: "쿨링",
    9: "가을 캠핑", 10: "환절기", 11: "난방",
}
_SEASON_EN = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "camping",
    6: "cooling", 7: "cooling", 8: "cooling",
    9: "fall", 10: "fall", 11: "heating",
}


class _KeywordsOut(BaseModel):
    keywords: list[str] = Field(description="검색 키워드 후보 5~8개, 터질 가능성 순")


class TrendAgent:
    name = "trend"
    role = "키워드 전략가 — 니치·시즌·타깃으로 오늘 검색할 키워드를 정한다"

    def __init__(self, llm=None, model: str = "claude-opus-4-8") -> None:
        self.llm = llm
        self.model = model

    @property
    def is_mock(self) -> bool:
        return self.llm is None

    def run(self, brief: Brief, log: AgentLog, count: int = 5) -> list[str]:
        """키워드 후보를 터질 가능성 순으로 반환. 항상 1개 이상."""
        if self.llm is not None:
            kws = self._claude(brief, count, log)
            if kws:
                return kws
        return self._mock(brief, count, log)

    # ------------------------------------------------------------------ #
    def _claude(self, brief: Brief, count: int, log: AgentLog) -> list[str]:
        lang = "영어" if brief.language == "en" else "한국어"
        niche = brief.niche or ("40+ daily convenience" if brief.language == "en" else "40대 이상 생활 편의")
        prompt = (
            f"오늘 날짜: {date.today().isoformat()} (시즌 반영)\n"
            f"마켓: {brief.market} / 언어: {lang} / 타깃: {brief.audience}\n"
            f"니치: {niche}\n\n"
            f"숏폼 제휴 콘텐츠로 터질 가능성이 높은 {lang} 상품 검색 키워드 {count}개를 "
            f"뽑아줘. 비주얼 임팩트가 크고 '이게 된다고?' 반응이 나올 상품 위주로."
        )
        try:
            resp = self.llm.messages.parse(
                model=self.model,
                max_tokens=500,
                thinking={"type": "adaptive"},
                system="너는 제휴 숏폼 키워드 전략가다. 검색량과 비주얼 임팩트를 함께 고려한다.",
                messages=[{"role": "user", "content": prompt}],
                output_format=_KeywordsOut,
            )
            out = resp.parsed_output
            if out and out.keywords:
                kws = [k.strip() for k in out.keywords if k.strip()][:count]
                log.add(f"[{brief.market}] Claude 키워드 {len(kws)}개: {kws}")
                return kws
        except Exception as e:
            log.add(f"[{brief.market}] Claude 키워드 실패({e}), mock 대체")
        return []

    def _mock(self, brief: Brief, count: int, log: AgentLog) -> list[str]:
        """니치·시즌 시드를 날짜로 로테이션 — 매일 다른 후보가 나온다."""
        pool_map = _POOL_EN if brief.language == "en" else _POOL_KO
        season_map = _SEASON_EN if brief.language == "en" else _SEASON_KO
        today = date.today()

        niche = (brief.niche or "").strip().lower()
        if niche and niche in pool_map:
            pool = list(pool_map[niche])
        else:
            # 니치 미지정: 전체 풀을 합쳐 타깃 무관 베스트 후보로
            pool = [k for kws in pool_map.values() for k in kws]

        # 날짜 기반 로테이션(결정적) — 같은 날은 같은 결과, 다음 날은 다른 후보
        offset = today.toordinal() % max(1, len(pool))
        rotated = pool[offset:] + pool[:offset]
        kws = rotated[:count]

        season = season_map.get(today.month)
        if season and len(kws) >= 2:
            kws[-1] = f"{season} {kws[-1]}"  # 마지막 후보에 시즌 보정
        log.add(f"[{brief.market}] mock 키워드(니치={niche or '전체'}, 시즌={season}): {kws}")
        return kws
