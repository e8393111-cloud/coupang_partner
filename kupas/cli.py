"""kupas 커맨드라인 — 분야별 에이전트 사슬을 구동한다.

예시:
    python -m kupas agents
    python -m kupas discover --keyword "캠핑 텐트" --top 5
    python -m kupas run --keyword "캠핑 텐트" --top 3 --vision
    python -m kupas list
    python -m kupas stats
"""

from __future__ import annotations

import argparse
import sys

from .agents.base import Brief
from .agents.orchestrator import Orchestrator
from .agents.publish import DISCLOSURE


def _brief(args: argparse.Namespace) -> Brief:
    platforms = tuple(args.platforms) if getattr(args, "platforms", None) else ("threads", "tiktok")
    top = getattr(args, "top", 3)
    return Brief(
        keyword=args.keyword,
        category_id=args.category,
        platforms=platforms,
        target_count=top,
        shortlist_size=max(top, 10),
        use_vision=getattr(args, "vision", False),
    )


def _print_logs(result) -> None:
    print("\n── 에이전트 로그 ──")
    for log in result.logs:
        for msg in log.messages:
            print(f"  [{log.agent}] {msg}")


def cmd_agents(_: argparse.Namespace) -> int:
    orch = Orchestrator()
    print(f"모드: {orch.mode_note}\n")
    print("── 에이전트 로스터 ──")
    for i, (name, role) in enumerate(orch.roster, 1):
        print(f"  {i}. {name:<10} {role}")
    print("\n흐름: discovery ▶ curation ▶ copy ▶ publish")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    orch = Orchestrator()
    print(f"모드: {orch.mode_note}")
    try:
        result = orch.curate(_brief(args))
    except ValueError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2
    print("\n── 선별 랭킹 (카피 미생성, 무료 triage) ──")
    for rank, s in enumerate(result.shortlist, 1):
        p = s.product
        print(f"\n[{rank}] 점수 {int(s.score.total):>4}  {p.name}  ({p.price:,}원, {p.category_name})")
        print(f"     근거: {', '.join(s.score.reasons)}")
    _print_logs(result)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    orch = Orchestrator()
    print(f"모드: {orch.mode_note}")
    try:
        result = orch.run(_brief(args), save=not args.no_save)
    except ValueError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2
    for i, piece in enumerate(result.pieces, 1):
        p = piece.product
        sc = int(piece.score.total) if piece.score else 0
        print(f"\n{'=' * 64}")
        print(f"[{i}] 점수 {sc}  {p.name}  ({p.price:,}원, {p.category_name})")
        print(f"딥링크: {piece.deeplink}   subId: {piece.sub_id}")
        for cap in piece.captions:
            print(f"\n  ── {cap.platform.upper()} ───────────────────────")
            for line in cap.render(piece.deeplink, DISCLOSURE).splitlines():
                print(f"  {line}")
    _print_logs(result)
    if not args.no_save:
        print(f"\n{len(result.pieces)}건 저장 완료 → {orch.config.db_path}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    storage = Orchestrator().storage
    rows = storage.list_content(limit=args.limit)
    if not rows:
        print("저장된 콘텐츠가 없습니다. 먼저 'run' 을 실행하세요.")
        return 0
    for r in rows:
        score = f"{r['score']:.0f}" if r["score"] is not None else "-"
        print(f"#{r['id']:>3}  점수 {score:>4}  {r['name'][:36]:<36}  {r['price']:>9,}원  {r['created_at']}")
    return 0


def cmd_stats(_: argparse.Namespace) -> int:
    s = Orchestrator().storage.summary()
    print("── 성과 요약 ──")
    print(f"게시(초안 포함): {s['posts']}건")
    print(f"클릭: {s['clicks']:,}   주문: {s['orders']:,}   추정 수수료: {s['revenue']:,}원")
    return 0


def cmd_perf(args: argparse.Namespace) -> int:
    Orchestrator().storage.record_performance(
        args.post_id, clicks=args.clicks, orders=args.orders, revenue=args.revenue
    )
    print(f"post #{args.post_id} 성과 반영 완료.")
    return 0


def _add_discovery_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--keyword", help="검색 키워드로 상품 발굴")
    p.add_argument("--category", type=int, help="카테고리 ID 로 베스트 상품 발굴")
    p.add_argument("--top", type=int, default=3, help="최종 선별 개수 (기본 3)")
    p.add_argument("--vision", action="store_true", help="Claude vision 신박도 점수 사용")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kupas", description="쿠팡 파트너스 숏폼 수익화 — 에이전트 파이프라인")
    sub = parser.add_subparsers(dest="command", required=True)

    pa = sub.add_parser("agents", help="에이전트 로스터·역할 출력")
    pa.set_defaults(func=cmd_agents)

    pd = sub.add_parser("discover", help="발굴+선별 랭킹만 (무료 triage)")
    _add_discovery_args(pd)
    pd.set_defaults(func=cmd_discover)

    pr = sub.add_parser("run", help="발굴→선별→카피→게시준비 전체 사슬")
    _add_discovery_args(pr)
    pr.add_argument(
        "--platforms", nargs="+", choices=["threads", "tiktok"],
        help="대상 플랫폼 (기본: threads tiktok)",
    )
    pr.add_argument("--no-save", action="store_true", help="DB 저장 생략")
    pr.set_defaults(func=cmd_run)

    pl = sub.add_parser("list", help="저장된 콘텐츠 목록")
    pl.add_argument("--limit", type=int, default=20)
    pl.set_defaults(func=cmd_list)

    ps = sub.add_parser("stats", help="성과 요약")
    ps.set_defaults(func=cmd_stats)

    pp = sub.add_parser("perf", help="게시물 성과 기록 (클릭/주문/수수료)")
    pp.add_argument("post_id", type=int)
    pp.add_argument("--clicks", type=int, default=0)
    pp.add_argument("--orders", type=int, default=0)
    pp.add_argument("--revenue", type=int, default=0)
    pp.set_defaults(func=cmd_perf)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
