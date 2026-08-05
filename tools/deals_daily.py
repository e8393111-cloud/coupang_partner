#!/usr/bin/env python3
"""하루특가 갱신 전 과정을 한 번에.

    python3 tools/deals_daily.py

    조회 → 쉐어링크 발급 → 페이지 생성 → 블로거 발행

왜 한 명령인가:
토스 API 는 등록된 출발지 IP 에서만 호출된다(CIDR 미지원, 2026-08-05 토스 확인).
그래서 이 작업은 고정 IP 가 있는 기기에서만 돌 수 있고, 그 기기 앞에 사람이
앉아 있는 시간은 짧다. 명령이 셋이면 하나를 빠뜨리고, 빠뜨린 걸 알아채는 건
며칠 뒤다 — 실제로 랜딩 페이지에서 한 번 겪었다(생성만 하고 반영을 잊었다).

필요한 환경변수:
    TOSS_ACCESS_KEY  TOSS_SECRET_KEY  TOSS_PUBLISHER_ID
    BLOGGER_CLIENT_ID  BLOGGER_CLIENT_SECRET  BLOGGER_REFRESH_TOKEN

--no-publish 를 주면 생성까지만 하고 멈춘다(확인용).
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join("deals_data", "today.json")
PAGE = os.path.join("blog", "deals", "today.html")
BLOG_CFG = os.path.join(ROOT, "deals_data", "blog.json")


def run(step, args):
    print(f"\n── {step} " + "─" * (58 - len(step)))
    r = subprocess.run([sys.executable, *args], cwd=ROOT)
    if r.returncode:
        raise SystemExit(f"\n✗ {step} 실패 — 여기서 멈춥니다. 위 메시지를 확인하세요.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-publish", action="store_true", help="생성까지만 하고 멈춘다")
    ap.add_argument("--countdown", action="store_true",
                    help="만료 카운트다운 스크립트를 넣는다 (블로그스팟 단속 상황을 보고 켤 것)")
    a = ap.parse_args()

    missing = [k for k in ("TOSS_ACCESS_KEY", "TOSS_SECRET_KEY", "TOSS_PUBLISHER_ID")
               if not os.environ.get(k)]
    if missing:
        raise SystemExit("✗ 환경변수가 없습니다: " + ", ".join(missing))

    run("① 하루특가 조회 · 쉐어링크 발급", ["tools/toss_api.py", "sync", DATA])
    gen = ["tools/make_deals.py", DATA]
    if a.countdown:
        gen.append("--countdown")
    run("② 페이지 생성", gen)

    if a.no_publish:
        print(f"\n생성까지 마쳤습니다: {PAGE}")
        print("확인 후 발행하려면 --no-publish 없이 다시 실행하세요.")
        return

    missing = [k for k in ("BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN")
               if not os.environ.get(k)]
    if missing:
        raise SystemExit("✗ 발행에 필요한 환경변수가 없습니다: " + ", ".join(missing) +
                         f"\n  페이지는 만들어졌습니다: {PAGE}")

    cfg = json.load(open(BLOG_CFG, encoding="utf-8"))
    # 새 페이지를 만들지 않고 기존 페이지를 갱신한다. 주소가 밀리면 북마크가 죽는다.
    run("③ 블로거 발행", ["tools/publish_blogger.py", "update",
                          cfg["pages"]["today"]["id"], PAGE, "--blog", cfg["blog"]])

    n = len([i for i in json.load(open(os.path.join(ROOT, DATA), encoding="utf-8")).get("items", [])
             if not i.get("isSoldOut")])
    print(f'\n✓ 완료 — https://{cfg["blog"]}{cfg["pages"]["today"]["url"]} · 상품 {n}건')
    print("  deals_data/ 변경분을 커밋해 두면 다음 실행 때 쉐어링크를 재사용합니다.")


if __name__ == "__main__":
    main()
