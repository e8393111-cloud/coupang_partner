#!/usr/bin/env python3
"""유튜브 쇼츠 검색을 파싱해 벤치마크 후보를 뽑는다.

    python3 tools/bench_shorts.py "자동급식기" --top 15
    python3 tools/bench_shorts.py "자동급식기" --write products/pawsie.shots.json

왜 이게 필요한가 (PLAN 「벤치마킹」):
- 훅을 감으로 정하면 매번 다시 감으로 정하게 된다. 조회수는 완벽하진 않아도
  **출처가 있는 근거**고, 카테고리마다 이기는 훅의 형태가 다르다.
- 실제로 「자동급식기」는 상위가 전부 부정·경고형이었다. "추천 TOP5" 류는 하위였다.
  이런 건 들여다보기 전에는 알 수 없다.

접근 경로 (2026-07-29 확인):
- ✅ 유튜브 쇼츠 검색은 `ytInitialData` 에 제목·조회수·videoId 가 그대로 들어온다
- ❌ watch 페이지의 `captionTracks` 는 막혔다 → 대본은 못 긁는다
- → 내용 분석은 MCP `video_analysis_create(youtube_url=...)` 로 한다 (이 스크립트 밖)

조회수는 전환이 아니다. 상위 목록은 "무엇이 클릭을 받나"까지만 말해준다.
"무엇이 구매로 이어지나"는 별개이고, 그건 온플랫폼 A/B 로만 답이 나온다.
"""
import argparse
import json
import os
import re
import subprocess
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
SHORTS_FILTER = "EgIYAQ%3D%3D"  # 검색 필터: 쇼츠만

# 훅 유형 분류 — 카테고리 불문 반복해서 이기는 형태들
PATTERNS = [
    ("경고형", r"주의|조심|사지\s*마|절대|하지\s*마세요|실수|후회"),
    ("부정형", r"안\s*쓰|안\s*사|싫|단점|망|별로|비추"),
    ("의문형", r"왜|이유|\?|어떻게|뭐가"),
    ("비교형", r"vs|비교|차이|대결"),
    ("후기형", r"후기|써\s*본|한\s*달|사용"),
    ("추천형", r"추천|BEST|TOP|베스트|가성비"),
]


def parse_views(txt):
    """'조회수 6.6만회' → 66000. 정렬용이라 근사치면 충분하다."""
    if not txt:
        return 0
    m = re.search(r"([\d.]+)\s*(억|만|천)?", txt.replace(",", ""))
    if not m:
        return 0
    n = float(m.group(1))
    return int(n * {"억": 1e8, "만": 1e4, "천": 1e3}.get(m.group(2), 1))


def classify(title):
    for name, pat in PATTERNS:
        if re.search(pat, title, re.I):
            return name
    return "기타"


def fetch(query, shorts_only=True):
    url = ("https://www.youtube.com/results?search_query="
           + urllib.parse.quote(query)
           + (f"&sp={SHORTS_FILTER}" if shorts_only else ""))
    r = subprocess.run(
        ["curl", "-sSL", "--max-time", "40", "-H", f"User-Agent: {UA}",
         "-H", "Accept-Language: ko-KR,ko;q=0.9", url],
        capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"검색 실패: {r.stderr[:200]}")
    return r.stdout


def extract(html):
    """ytInitialData 를 훑어 (videoId, 제목, 조회수) 를 모은다.

    유튜브는 렌더러 구조를 자주 바꾼다. 특정 경로를 하드코딩하지 않고
    트리 전체를 걸어가며 필요한 모양을 만나면 줍는 식으로 버틴다.
    """
    m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});</script>", html, re.S)
    if not m:
        raise SystemExit("ytInitialData 를 못 찾았다 — 유튜브가 구조를 바꿨을 수 있다")
    data = json.loads(m.group(1))
    rows = []

    def walk(o):
        if isinstance(o, dict):
            # 쇼츠 카드
            if "onTap" in o and "overlayMetadata" in o:
                om = o.get("overlayMetadata") or {}
                title = (om.get("primaryText") or {}).get("content")
                views = (om.get("secondaryText") or {}).get("content")
                try:
                    vid = o["onTap"]["innertubeCommand"]["reelWatchEndpoint"]["videoId"]
                except Exception:
                    vid = None
                if title and vid:
                    rows.append({"video_id": vid, "title": title, "views_text": views})
            # 일반 영상 카드
            elif "videoId" in o and "title" in o:
                t = o.get("title") or {}
                txt = None
                if isinstance(t, dict):
                    txt = (t.get("runs") or [{}])[0].get("text") or t.get("simpleText")
                if txt:
                    vt = o.get("viewCountText") or {}
                    rows.append({"video_id": o["videoId"], "title": txt,
                                 "views_text": vt.get("simpleText") if isinstance(vt, dict) else None})
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    seen, out = set(), []
    for r in rows:
        if r["video_id"] in seen:
            continue
        seen.add(r["video_id"])
        r["views"] = parse_views(r["views_text"])
        r["hook_type"] = classify(r["title"])
        r["url"] = f"https://www.youtube.com/shorts/{r['video_id']}"
        out.append(r)
    return sorted(out, key=lambda x: -x["views"])


def summarize(rows, top):
    """유형별 중앙 조회수. 어떤 훅이 이기는지 한 줄로 보여준다."""
    from statistics import median
    buckets = {}
    for r in rows[:top]:
        buckets.setdefault(r["hook_type"], []).append(r["views"])
    return sorted(((k, len(v), int(median(v))) for k, v in buckets.items()),
                  key=lambda x: -x[2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--all", action="store_true", help="쇼츠 외 일반 영상도 포함")
    ap.add_argument("--write", help="shots json 의 benchmark 블록에 기록")
    args = ap.parse_args()

    rows = extract(fetch(args.query, shorts_only=not args.all))
    print(f'"{args.query}" — {len(rows)}건\n')
    print(f'{"조회수":>10}  {"유형":<6}  제목')
    print("-" * 78)
    for r in rows[:args.top]:
        print(f'{r["views"]:>10,}  {r["hook_type"]:<6}  {r["title"][:44]}')

    print(f"\n훅 유형별 중앙 조회수 (상위 {args.top}건)")
    print("-" * 78)
    for name, n, med in summarize(rows, args.top):
        print(f"  {name:<6} {n:>2}건  중앙 {med:>10,}")

    if args.write:
        path = args.write if os.path.isabs(args.write) else os.path.join(ROOT, args.write)
        cfg = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
        cfg["benchmark"] = {
            "_": "bench_shorts.py 가 기록. 훅 설계의 출처. 조회수는 전환이 아니다.",
            "query": args.query,
            "by_hook_type": [{"type": n, "n": c, "median_views": m}
                             for n, c, m in summarize(rows, args.top)],
            "refs": [{**r, "analysis_job": None, "hook_beats": None, "notes": None}
                     for r in rows[:args.top]],
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"\n기록: {path}")


if __name__ == "__main__":
    main()
