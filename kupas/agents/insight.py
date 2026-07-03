"""인사이트 에이전트 — 성과 데이터를 학습으로 되먹인다 (루프 클로저).

storage 에 쌓인 클릭·주문·수수료를 카테고리/플랫폼별로 분석해
(1) 사람이 읽을 리포트와 (2) CurationAgent 에 주입할 카테고리 부스트를 만든다.
"터진 카테고리"의 다음 상품이 선별 상위로 올라오면서, 던지고→배우는 루프가 닫힌다.

Claude 불필요 — 순수 집계. 데이터가 적을 땐(클릭 임계 미달) 부스트를 내지 않는다
(소표본 과적합 방지).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..storage import Storage
from .base import AgentLog

# 부스트를 낼 최소 근거 — 이보다 적으면 노이즈로 보고 학습하지 않는다
MIN_TOTAL_CLICKS = 30
MAX_BOOST = 40.0  # curation 40+ 가점과 같은 스케일


@dataclass
class InsightReport:
    total: dict = field(default_factory=dict)          # posts/clicks/orders/revenue
    by_category: list[dict] = field(default_factory=list)
    by_platform: list[dict] = field(default_factory=list)
    category_boosts: dict[str, float] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)


class InsightAgent:
    name = "insight"
    role = "성과 분석가 — 터진 카테고리·플랫폼을 찾아 선별 점수에 되먹인다"

    def run(self, storage: Storage, log: AgentLog) -> InsightReport:
        report = InsightReport(
            total=storage.summary(),
            by_category=storage.perf_by_category(),
            by_platform=storage.perf_by_platform(),
        )
        report.category_boosts = self._boosts(report, log)
        report.recommendations = self._recommend(report)
        return report

    def category_boosts(self, storage: Storage) -> dict[str, float]:
        """오케스트레이터용 간편 진입점 — 근거 부족하면 {} (부스트 없음)."""
        return self.run(storage, AgentLog(self.name)).category_boosts

    # ------------------------------------------------------------------ #
    def _boosts(self, report: InsightReport, log: AgentLog) -> dict[str, float]:
        total_clicks = int(report.total.get("clicks", 0) or 0)
        if total_clicks < MIN_TOTAL_CLICKS:
            log.add(f"클릭 {total_clicks}건 < {MIN_TOTAL_CLICKS} — 학습 보류(소표본)")
            return {}

        total_rev = sum(int(r["revenue"] or 0) for r in report.by_category)
        boosts: dict[str, float] = {}
        for row in report.by_category:
            cat, rev = row["category"], int(row["revenue"] or 0)
            if not cat or rev <= 0:
                continue
            share = rev / total_rev if total_rev else 0.0
            boosts[cat.lower()] = round(MAX_BOOST * share, 1)
        if boosts:
            log.add("카테고리 부스트: " + ", ".join(f"{k}+{v:g}" for k, v in boosts.items()))
        return boosts

    def _recommend(self, report: InsightReport) -> list[str]:
        recs: list[str] = []
        cats = [r for r in report.by_category if int(r["revenue"] or 0) > 0]
        if cats:
            top = cats[0]
            recs.append(
                f"'{top['category']}' 카테고리가 수수료 {top['revenue']:,}원으로 최고 — "
                f"이 니치의 상품·후킹을 늘리세요."
            )
        plats = [r for r in report.by_platform if int(r["clicks"] or 0) > 0]
        if len(plats) >= 2:
            best, worst = plats[0], plats[-1]
            if int(best["revenue"] or 0) > int(worst["revenue"] or 0) * 2:
                recs.append(
                    f"{best['platform']} 가 {worst['platform']} 대비 수익 2배 이상 — "
                    f"게시 비중을 {best['platform']} 쪽으로."
                )
        zero = [r["category"] for r in report.by_category
                if int(r["clicks"] or 0) == 0 and int(r["posts"] or 0) >= 3]
        if zero:
            recs.append(f"게시 3건 이상인데 클릭 0인 카테고리 {zero} — 후킹/상품 교체 검토.")
        if not recs:
            recs.append("아직 유의미한 패턴 없음 — 게시를 늘려 데이터를 쌓으세요.")
        return recs
