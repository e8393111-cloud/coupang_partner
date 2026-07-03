"""검수 에이전트 — 카피가 나가기 전에 법적·플랫폼 리스크를 걸러낸다.

40+ 타깃은 건강 제품 비중이 높아 효능 단정("치료된다")·과장("100% 효과") 표현이
나오기 쉽다. 한국 표시광고법·의료기기법, 미국 FTC 가이드 기준으로 위험 표현을
탐지하고 안전한 표현으로 순화한다.

규칙 기반(무료·항상 실행)이 1차 방어선이고, Claude 가 있으면 순화 문장을 자연스럽게
다듬는다(선택). 사슬 위치: Copy 다음, Media/Publish 앞 — 순화된 카피가 TTS 대본과
렌더본에 반영되도록.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models import Caption
from .base import AgentLog, Brief

# ── 규칙: 위험 표현 → 순화 표현 ────────────────────────────────────
# (패턴, 대체어, 사유) — 대체어 None 이면 자동 순화 불가, 플래그만
_RULES_KO: list[tuple[str, str | None, str]] = [
    (r"치료", "관리", "의료 효능 단정(의료기기법·표시광고법 위험)"),
    (r"완치", "개선", "의료 효능 단정"),
    (r"질병\s*예방", "건강 관리", "질병 예방 효능 단정"),
    (r"부작용\s*(이|가)?\s*없", "순한 사용감", "안전성 단정"),
    (r"100\s*%\s*(효과|보장)", "만족도 높은", "절대적 효능 보장"),
    (r"무조건", "많은 분들이", "절대적 표현"),
    (r"살(이)?\s*빠지", "가볍게 관리", "다이어트 효능 단정"),
    (r"의사\s*(추천|권장)", None, "전문가 보증 표현(근거 필요)"),
    (r"국내\s*최저가|최저가\s*보장", None, "최저가 보장(가격 변동 리스크)"),
]
_RULES_EN: list[tuple[str, str | None, str]] = [
    (r"\bcure(s|d)?\b", "help with", "medical claim (FTC)"),
    (r"\btreat(s|ment)?\b", "support", "medical claim (FTC)"),
    (r"\bguarantee(d|s)?\b", "designed to", "absolute guarantee"),
    (r"\bFDA[- ]approved\b", None, "regulatory claim (needs proof)"),
    (r"\b100%\s*(effective|safe)\b", "well-reviewed", "absolute efficacy/safety claim"),
    (r"\bno side effects?\b", "gentle", "safety claim"),
    (r"\bdoctor[- ](recommended|approved)\b", None, "expert endorsement (needs proof)"),
    (r"\blose weight\b", "feel lighter", "weight-loss claim"),
]


@dataclass
class ComplianceIssue:
    platform: str
    pattern: str
    reason: str
    fixed: bool          # 자동 순화 성공 여부
    before: str = ""
    after: str = ""


@dataclass
class ComplianceReport:
    issues: list[ComplianceIssue] = field(default_factory=list)

    @property
    def flagged(self) -> list[ComplianceIssue]:
        """자동 순화 못한 건 — 사람이 게시 전에 확인해야 한다."""
        return [i for i in self.issues if not i.fixed]


class ComplianceAgent:
    name = "compliance"
    role = "검수 문지기 — 효능 단정·과장 표현을 법규 기준으로 탐지·순화"

    def __init__(self, llm=None, model: str = "claude-opus-4-8") -> None:
        self.llm = llm
        self.model = model

    def run(
        self, brief: Brief, captions: list[Caption], log: AgentLog
    ) -> tuple[list[Caption], ComplianceReport]:
        """카피를 검수해 (순화된 카피, 리포트) 반환. 카피는 제자리 수정."""
        rules = _RULES_EN if brief.language == "en" else _RULES_KO
        report = ComplianceReport()

        for cap in captions:
            for attr in ("hook", "body"):
                text = getattr(cap, attr)
                new_text, found = self._apply_rules(text, rules, cap.platform, report)
                if found:
                    setattr(cap, attr, new_text)
            cap.alt_hooks = [
                self._apply_rules(h, rules, cap.platform, report)[0] for h in cap.alt_hooks
            ]

        if report.issues:
            fixed = sum(1 for i in report.issues if i.fixed)
            log.add(
                f"위험 표현 {len(report.issues)}건 탐지 (자동 순화 {fixed}건, "
                f"수동 확인 필요 {len(report.flagged)}건)"
            )
            for i in report.flagged:
                log.add(f"⚠ [{i.platform}] '{i.pattern}' — {i.reason} (게시 전 확인)")
        else:
            log.add("위험 표현 없음 — 통과")
        return captions, report

    # ------------------------------------------------------------------ #
    def _apply_rules(
        self,
        text: str,
        rules: list[tuple[str, str | None, str]],
        platform: str,
        report: ComplianceReport,
    ) -> tuple[str, bool]:
        found = False
        for pattern, replacement, reason in rules:
            if not re.search(pattern, text, flags=re.IGNORECASE):
                continue
            found = True
            before = text
            if replacement is not None:
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
                report.issues.append(ComplianceIssue(
                    platform=platform, pattern=pattern, reason=reason,
                    fixed=True, before=before, after=text,
                ))
            else:
                report.issues.append(ComplianceIssue(
                    platform=platform, pattern=pattern, reason=reason, fixed=False,
                ))
        return text, found
