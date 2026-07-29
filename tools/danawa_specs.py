#!/usr/bin/env python3
"""다나와에서 상품 후보 + 모델명 + 사양 + 시세를 뽑아 글 데이터 뼈대를 만든다.

쿠팡·토스쇼핑은 이 세션에서 접근이 막혀 있고, 쿠팡 파트너스 Open API 는
누적 수익 15만원을 넘겨야 신청할 수 있다. 그래서 **사양과 후보 선정은 다나와로 하고,
실제 판매가와 제휴 링크만 사용자가 채우는** 구조로 나눈다.

사용법:
    python3 tools/danawa_specs.py "강아지 자동급식기" --id feeder
    python3 tools/danawa_specs.py "펫드라이룸" --id dryroom --count 8 --min 50000

출력: posts_data/<id>.json  (coupang/toss 는 비어 있음 → 사용자가 채움)

⚠️ 다나와 시세는 **참고용**이다. 글에 싣는 가격은 반드시 쿠팡·토스 실제 페이지 기준이어야 한다.
"""
import argparse
import html
import json
import os
import re
import subprocess
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def fetch(url):
    r = subprocess.run(["curl", "-sS", "-A", UA, "--max-time", "30", url],
                       capture_output=True, text=True)
    return r.stdout


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def parse_spec(spec_text):
    """다나와 사양 문자열('용량: 3.6L/스마트폰 연동/...') → 우리 스키마.

    없는 정보는 추측하지 않고 None/False 로 두고 note 에 남긴다.
    """
    parts = [p.strip() for p in spec_text.split("/") if p.strip()]
    out = {"capacity_l": None, "wet_food": False, "power": "", "blackout_backup": False,
           "app": False, "camera": False, "washable": "", "noise_db": None}
    unknown = []
    for p in parts:
        low = p.replace(" ", "")
        m = re.search(r"용량:?\s*([\d.]+)\s*[LlㄹŁ리터]", p)
        if m:
            out["capacity_l"] = float(m.group(1))
            continue
        if "스마트폰" in low or "앱" == low or "wifi" in low.lower() or "와이파이" in low:
            out["app"] = True
            continue
        if any(k in low for k in ("cctv", "홈캠", "카메라")):
            out["camera"] = True
            continue
        if "습식" in low:
            out["wet_food"] = True
            continue
        if any(k in low for k in ("건전지", "배터리", "충전")):
            out["power"] = (out["power"] + " " + p).strip()
            out["blackout_backup"] = True
            continue
        if "어댑터" in low or "전원" in low:
            out["power"] = (out["power"] + " " + p).strip()
            continue
        if "분리" in low and "세척" in low:
            out["washable"] = p
            continue
        unknown.append(p)
    return out, unknown


def search(keyword, count, pmin, pmax):
    q = urllib.parse.quote(keyword)
    h = fetch(f"https://search.danawa.com/dsearch.php?query={q}&sort=saveDESC")
    blocks = re.findall(r'<li[^>]*class="prod_item[^"]*"[^>]*>(.*?)</li>', h, re.S)
    items = []
    for b in blocks:
        nm = re.search(r'class="prod_name"[^>]*>\s*<a[^>]*>(.*?)</a>', b, re.S)
        pr = re.search(r'class="price_sect"[^>]*>.*?<strong>(.*?)</strong>', b, re.S)
        sp = re.search(r'class="spec_list"[^>]*>(.*?)</div>', b, re.S)
        if not nm:
            continue
        name = clean(nm.group(1))
        price = None
        if pr:
            digits = re.sub(r"[^\d]", "", clean(pr.group(1)))
            price = int(digits) if digits else None
        if price is None:
            continue
        if pmin and price < pmin:
            continue
        if pmax and price > pmax:
            continue
        spec_text = clean(sp.group(1)) if sp else ""
        spec, unknown = parse_spec(spec_text)

        # 이름에서 모델명 후보 추출 (영문+숫자 조합)
        mm = re.search(r"\b([A-Z][A-Za-z]*[-_]?\d[\w-]*)\b", name)
        brand = name.split()[0] if name else ""

        note = []
        if not spec["capacity_l"]:
            note.append("용량 확인 필요")
        if not spec["power"]:
            note.append("전원 방식 확인 필요")
        if unknown:
            note.append("다나와 표기: " + ", ".join(unknown[:4]))

        items.append({
            "name": name,
            "brand": brand,
            "model": mm.group(1) if mm else "",
            "danawa_price": price,
            "coupang": None,
            "toss": None,
            "spec": spec,
            "note": " · ".join(note),
            "links": {"coupang": "", "toss": ""},
        })
        if len(items) >= count * 3:
            break
    return items


def quality(item):
    """사양이 충실한 제품을 우선한다.

    오픈마켓식 키워드 나열 상품은 사양이 비어 있어 비교표를 못 채운다.
    비교 글의 품질은 결국 사양 데이터의 밀도에서 갈리므로 이걸 1차 기준으로 둔다.
    """
    sp, s = item["spec"], 0
    if sp["capacity_l"]:
        s += 3            # 용량은 비교표의 핵심 축
    if item["model"]:
        s += 2            # 모델명이 있어야 쿠팡·토스에서 같은 물건인지 대조 가능
    s += sum(1 for k in ("app", "camera", "wet_food", "blackout_backup") if sp[k])
    if sp["power"]:
        s += 1
    # 키워드 나열형 긴 이름은 감점
    if len(item["name"]) > 45:
        s -= 1
    return s


def spread(items, count):
    """사양이 충실한 것들 중에서 가격대를 고르게 섞는다(가성비/표준/프리미엄)."""
    if len(items) <= count:
        return items
    # 상위 품질군을 넉넉히 남긴 뒤 그 안에서 가격 분산
    pool = sorted(items, key=quality, reverse=True)[:max(count * 2, 8)]
    s = sorted(pool, key=lambda x: x["danawa_price"])
    picked, step = [], len(s) / count
    for i in range(count):
        picked.append(s[int(i * step)])
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keyword")
    ap.add_argument("--id", required=True, help="posts_data/<id>.json")
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--min", type=int, default=0, dest="pmin")
    ap.add_argument("--max", type=int, default=0, dest="pmax")
    args = ap.parse_args()

    found = search(args.keyword, args.count, args.pmin, args.pmax)
    if not found:
        raise SystemExit("검색 결과 없음 — 키워드나 가격 범위를 바꿔보세요")
    items = spread(found, args.count)

    out_path = os.path.join(ROOT, "posts_data", f"{args.id}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "category": args.keyword,
            "checked_at": "",
            "_주의": "danawa_price 는 시세 참고용. 글에 싣는 가격은 쿠팡·토스 실제 페이지 기준이어야 한다.",
            "items": items,
        }, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"후보 {len(found)}개 중 {len(items)}개 선정 → {out_path}\n")
    for i in items:
        sp = i["spec"]
        bits = [f'{sp["capacity_l"]}L' if sp["capacity_l"] else "용량?",
                "앱" if sp["app"] else "", "카메라" if sp["camera"] else "",
                "배터리" if sp["blackout_backup"] else ""]
        print(f'  {i["danawa_price"]:>9,}원  {i["name"][:44]:<46} {" ".join(b for b in bits if b)}')
    print("\n다음: 위 제품들의 쿠팡·토스 실제 가격과 링크를 채운 뒤")
    print(f"      python3 tools/make_blogpost.py posts_data/{args.id}.json")


if __name__ == "__main__":
    main()
