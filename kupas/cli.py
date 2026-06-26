"""kupas 커맨드라인 인터페이스.

예시:
    python -m kupas run --keyword "캠핑 텐트" --limit 3
    python -m kupas run --category 1016 --limit 5
    python -m kupas list
    python -m kupas stats
"""

from __future__ import annotations

import argparse
import sys

from .config import Config
from .pipeline import DISCLOSURE, Pipeline


def _print_piece(piece, index: int) -> None:
    p = piece.product
    print(f"\n{'=' * 64}")
    print(f"[{index}] {p.name}  ({p.price:,}원, {p.category_name})")
    print(f"딥링크: {piece.deeplink}   subId: {piece.sub_id}")
    for cap in piece.captions:
        print(f"\n  ── {cap.platform.upper()} ───────────────────────────")
        text = cap.render(piece.deeplink, DISCLOSURE)
        for line in text.splitlines():
            print(f"  {line}")


def cmd_run(args: argparse.Namespace) -> int:
    pipe = Pipeline()
    print(f"모드: {pipe.mode_note}")
    platforms = tuple(args.platforms) if args.platforms else ("threads", "tiktok")
    try:
        pieces = pipe.run(
            keyword=args.keyword,
            category_id=args.category,
            limit=args.limit,
            platforms=platforms,
            save=not args.no_save,
        )
    except ValueError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2
    for i, piece in enumerate(pieces, 1):
        _print_piece(piece, i)
    if not args.no_save:
        print(f"\n{len(pieces)}건 저장 완료 → {pipe.config.db_path}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    storage = Pipeline().storage
    rows = storage.list_content(limit=args.limit)
    if not rows:
        print("저장된 콘텐츠가 없습니다. 먼저 'run' 을 실행하세요.")
        return 0
    for r in rows:
        print(f"#{r['id']:>3}  {r['name'][:40]:<40}  {r['price']:>9,}원  {r['created_at']}")
    return 0


def cmd_stats(_: argparse.Namespace) -> int:
    s = Pipeline().storage.summary()
    print("── 성과 요약 ──")
    print(f"게시(초안 포함): {s['posts']}건")
    print(f"클릭: {s['clicks']:,}   주문: {s['orders']:,}   추정 수수료: {s['revenue']:,}원")
    return 0


def cmd_perf(args: argparse.Namespace) -> int:
    Pipeline().storage.record_performance(
        args.post_id, clicks=args.clicks, orders=args.orders, revenue=args.revenue
    )
    print(f"post #{args.post_id} 성과 반영 완료.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kupas", description="쿠팡 파트너스 숏폼 수익화 파이프라인")
    sub = parser.add_subparsers(dest="command", required=True)

    pr = sub.add_parser("run", help="발굴→카피→딥링크 실행")
    pr.add_argument("--keyword", help="검색 키워드로 상품 발굴")
    pr.add_argument("--category", type=int, help="카테고리 ID 로 베스트 상품 발굴")
    pr.add_argument("--limit", type=int, default=5, help="상품 개수 (기본 5)")
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
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
