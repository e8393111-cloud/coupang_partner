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
        niche=getattr(args, "niche", None),
        platforms=platforms,
        target_count=top,
        shortlist_size=max(top, 10),
        use_vision=getattr(args, "vision", False),
        with_media=getattr(args, "media", False),
        market=getattr(args, "market", "kr"),
        audience=getattr(args, "audience", "general"),
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
    print(f"모드: {orch.mode_note}  |  마켓: {args.market}")
    try:
        result = orch.curate_markets(_brief(args))
    except ValueError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2
    print("\n── 선별 랭킹 (카피 미생성, 무료 triage) ──")
    for rank, s in enumerate(result.shortlist, 1):
        p = s.product
        print(f"\n[{rank}] 점수 {int(s.score.total):>4}  {p.name}  ({p.price:,} {p.category_name})")
        print(f"     근거: {', '.join(s.score.reasons)}")
    _print_logs(result)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    orch = Orchestrator()
    print(f"모드: {orch.mode_note}  |  마켓: {args.market}")
    try:
        result = orch.run_markets(_brief(args), save=not args.no_save)
    except ValueError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2
    for i, piece in enumerate(result.pieces, 1):
        p = piece.product
        sc = int(piece.score.total) if piece.score else 0
        print(f"\n{'=' * 64}")
        print(f"[{i}] 점수 {sc}  {p.name}  ({p.price:,} {p.category_name})")
        print(f"딥링크: {piece.deeplink}   subId: {piece.sub_id}")
        for cap in piece.captions:
            print(f"\n  ── {cap.platform.upper()} ───────────────────────")
            # 저장된 렌더본(플랫폼별 링크·언어별 고지 포함)을 그대로 출력
            text = piece.rendered.get(cap.platform) or cap.render(
                piece.platform_links.get(cap.platform, piece.deeplink), DISCLOSURE
            )
            for line in text.splitlines():
                print(f"  {line}")
            if cap.alt_hooks:
                print(f"  · 대체 후킹(A/B): {' / '.join(cap.alt_hooks)}")
        for mb in piece.media:
            print(f"\n  ── 🎬 미디어 기획 [{mb.platform.upper()}] {mb.format} ─────")
            for j, shot in enumerate(mb.shots, 1):
                dur = f"{shot.seconds:g}s" if shot.seconds else "슬라이드"
                print(f"     {j}. ({dur}) {shot.visual}  | 자막: {shot.overlay}")
            print(f"     BGM: {mb.music}")
            if mb.tts_script:
                print(f"     📝 캡컷 TTS 대본: {mb.tts_script}")
            if mb.image_prompts:
                print(f"     🖼  이미지 프롬프트: {mb.image_prompts[0]}")
            if mb.video_prompt:
                print(f"     🎬 영상 프롬프트: {mb.video_prompt}")
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


def cmd_queue(_: argparse.Namespace) -> int:
    rows = Orchestrator().storage.export_queue()
    if not rows:
        print("게시 대기 중인 항목이 없습니다.")
        return 0
    print(f"── 게시 큐 ({len(rows)}건) ──")
    for r in rows:
        when = r["scheduled_at"] or "즉시"
        print(f"post #{r['post_id']:>3}  [{r['platform']}]  예약: {when}  {r['deeplink']}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    import csv as _csv
    import json as _json

    rows = Orchestrator().storage.export_queue()
    if args.format == "json":
        with open(args.out, "w", encoding="utf-8") as f:
            _json.dump(rows, f, ensure_ascii=False, indent=2)
    else:
        with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
            w = _csv.DictWriter(
                f, fieldnames=["post_id", "platform", "scheduled_at", "deeplink", "sub_id", "caption"]
            )
            w.writeheader()
            for r in rows:
                w.writerow(r)
    print(f"게시 큐 {len(rows)}건 → {args.out} ({args.format})")
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    Orchestrator().storage.schedule_post(args.post_id, args.at)
    print(f"post #{args.post_id} 예약: {args.at}")
    return 0


def cmd_import_report(args: argparse.Namespace) -> int:
    from .report import parse_coupang_report

    try:
        report = parse_coupang_report(args.csv_path)
    except (OSError, ValueError) as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2
    updated = Orchestrator().storage.import_report(report)
    print(f"리포트 {len(report)}개 subId 파싱, post {updated}건 성과 반영.")
    if updated == 0 and report:
        print("(매칭된 subId 가 없습니다. subId 접두/플랫폼 설정을 확인하세요.)")
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    import json as _json

    import requests

    orch = Orchestrator()
    url = args.webhook or orch.config.make_webhook
    if not url:
        print("웹훅 URL 이 없습니다. --webhook 또는 KUPAS_MAKE_WEBHOOK 설정 필요.", file=sys.stderr)
        return 2
    rows = orch.storage.export_queue()
    if not rows:
        print("보낼 게시 큐가 없습니다.")
        return 0
    try:
        resp = requests.post(url, json={"posts": rows}, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"웹훅 전송 실패: {e}", file=sys.stderr)
        return 1
    print(f"게시 큐 {len(rows)}건을 Make 웹훅으로 전송 완료 (status {resp.status_code}).")
    return 0


def cmd_perf(args: argparse.Namespace) -> int:
    Orchestrator().storage.record_performance(
        args.post_id, clicks=args.clicks, orders=args.orders, revenue=args.revenue
    )
    print(f"post #{args.post_id} 성과 반영 완료.")
    return 0


def _add_discovery_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--keyword", help="검색 키워드 (생략 시 TrendAgent 가 자동 발굴)")
    p.add_argument("--category", type=int, help="카테고리 ID 로 베스트 상품 발굴")
    p.add_argument("--niche", help="니치(주제) — 키워드 자동 발굴의 힌트 (예: 건강, 주방, kitchen)")
    p.add_argument("--top", type=int, default=3, help="최종 선별 개수 (기본 3)")
    p.add_argument("--vision", action="store_true", help="Claude vision 신박도 점수 사용")
    p.add_argument(
        "--market", default="kr", choices=["kr", "global", "ali", "all"],
        help="마켓: kr(쿠팡/한국어) | global(Amazon/영어) | ali(AliExpress/영어) | all(국내+글로벌 동시)",
    )
    p.add_argument("--audience", default="general", help="타깃 (예: 40+ → 관련 카테고리 가점)")


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
        "--platforms", nargs="+", choices=["threads", "tiktok", "reels", "shorts"],
        help="대상 플랫폼 (기본: threads tiktok / 40+는 reels shorts 권장)",
    )
    pr.add_argument("--media", action="store_true", help="틱톡·릴스 소재 기획서 생성")
    pr.add_argument("--no-save", action="store_true", help="DB 저장 생략")
    pr.set_defaults(func=cmd_run)

    pl = sub.add_parser("list", help="저장된 콘텐츠 목록")
    pl.add_argument("--limit", type=int, default=20)
    pl.set_defaults(func=cmd_list)

    ps = sub.add_parser("stats", help="성과 요약")
    ps.set_defaults(func=cmd_stats)

    pq = sub.add_parser("queue", help="게시 대기 큐 보기")
    pq.set_defaults(func=cmd_queue)

    pe = sub.add_parser("export", help="게시 큐를 파일로 내보내기 (Make/Buffer 연동)")
    pe.add_argument("--out", default="kupas_queue.csv", help="출력 파일 경로")
    pe.add_argument("--format", choices=["csv", "json"], default="csv")
    pe.set_defaults(func=cmd_export)

    psc = sub.add_parser("schedule", help="게시물 예약 시각 지정")
    psc.add_argument("post_id", type=int)
    psc.add_argument("--at", required=True, help="예약 시각 'YYYY-MM-DD HH:MM'")
    psc.set_defaults(func=cmd_schedule)

    pir = sub.add_parser("import-report", help="파트너스 리포트 CSV 로 성과 자동 수집")
    pir.add_argument("csv_path", help="쿠팡 파트너스 리포트 CSV 경로")
    pir.set_defaults(func=cmd_import_report)

    ppush = sub.add_parser("push", help="게시 큐를 Make 웹훅으로 전송 (반자동 게시)")
    ppush.add_argument("--webhook", help="웹훅 URL (미지정 시 KUPAS_MAKE_WEBHOOK)")
    ppush.set_defaults(func=cmd_push)

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
