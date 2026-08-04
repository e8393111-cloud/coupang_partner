#!/usr/bin/env python3
"""토스쇼핑 쉐어링크 Open API 클라이언트.

    export TOSS_ACCESS_KEY=...  TOSS_SECRET_KEY=...  TOSS_PUBLISHER_ID=...
    python3 tools/toss_api.py health
    python3 tools/toss_api.py whoami                     # 내 출발지 IP 확인
    python3 tools/toss_api.py best --size 20
    python3 tools/toss_api.py categories
    python3 tools/toss_api.py category-best <categoryId>
    python3 tools/toss_api.py deals
    python3 tools/toss_api.py detail 12345,12346
    python3 tools/toss_api.py link 12345                 # 쉐어링크 발급
    python3 tools/toss_api.py refresh posts_data/feeder.json   # 저장된 상품 가격 갱신

🔴 키를 파일에 쓰지 마세요. 이 repo 는 공개입니다. 환경변수로만 넘깁니다.
   --alpha 를 붙이면 알파(테스트) 환경으로 갑니다.

설계 근거 (문서 실측):
- 응답은 HTTP 200 이어도 실패일 수 있다 → **resultType 으로 판별**한다.
- 호출 한도 파트너 단위 10rps · 버스트 30 → 기본 간격을 두고, 429 는 Retry-After 를 따른다.
- 400/401/403/404 는 재시도하지 않는다(요청·자격 문제라 결과가 같다).
- 토큰은 유효기간이 길다(약 1년) → 파일에 캐시해 재사용한다. 매번 발급하면 이용이 제한된다.
- 출발지 IP 가 등록돼 있어야 한다. 미등록이면 전 호출이 IP_NOT_ALLOWED.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_CACHE = os.path.join(ROOT, ".toss_token.json")   # .gitignore 대상

ENVS = {
    "prod":  ("https://sharelink.toss.im/openapi", "https://oauth2.cert.toss.im/token"),
    "alpha": ("https://alpha-sharelink.toss.im/openapi", "https://oauth2-alpha.cert.toss.im/token"),
}
MIN_INTERVAL = 0.12          # 10rps 한도 아래로 여유 있게
_last_call = [0.0]


def die(msg):
    raise SystemExit(f"✗ {msg}")


def curl(args, timeout=40):
    r = subprocess.run(["curl", "-sS", "--max-time", str(timeout), *args],
                       capture_output=True, text=True)
    if r.returncode:
        die(f"네트워크 오류: {r.stderr.strip()[:200]}")
    return r.stdout


def egress_ip():
    return curl(["https://api.ipify.org"], timeout=20).strip()


# ───────────────────────── 인증 ─────────────────────────

def get_token(env, scope="sharelink:read sharelink:write", force=False):
    base, token_url = ENVS[env]
    if not force and os.path.exists(TOKEN_CACHE):
        c = json.load(open(TOKEN_CACHE))
        if c.get("env") == env and c.get("expires_at", 0) > time.time() + 300:
            return c["access_token"]

    ak, sk = os.environ.get("TOSS_ACCESS_KEY"), os.environ.get("TOSS_SECRET_KEY")
    if not (ak and sk):
        die("TOSS_ACCESS_KEY / TOSS_SECRET_KEY 환경변수가 없습니다.\n"
            "  export TOSS_ACCESS_KEY=... TOSS_SECRET_KEY=...")

    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": ak, "client_secret": sk, "scope": scope})
    out = curl(["-X", "POST", token_url,
                "-H", "Content-Type: application/x-www-form-urlencoded",
                "-d", body])
    try:
        d = json.loads(out)
    except json.JSONDecodeError:
        die(f"토큰 응답 파싱 실패: {out[:300]}")
    if "access_token" not in d:
        die(f"토큰 발급 실패: {json.dumps(d, ensure_ascii=False)[:300]}")

    # 유효기간이 길다 → 캐시해서 재사용한다. 매 호출 발급은 이용 제한 사유.
    with open(TOKEN_CACHE, "w") as f:
        json.dump({"env": env, "access_token": d["access_token"],
                   "expires_at": time.time() + int(d.get("expires_in", 3600))}, f)
    os.chmod(TOKEN_CACHE, 0o600)
    print(f"  토큰 발급 · 유효 {int(d.get('expires_in', 0)) // 86400}일 · 캐시 저장", file=sys.stderr)
    return d["access_token"]


# ───────────────────────── 호출 ─────────────────────────

def call(env, path, token, method="GET", params=None, body=None, _try=0):
    base, _ = ENVS[env]
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    args = ["-H", f"Authorization: Bearer {token}", "-D", "/tmp/.toss_hdr"]
    if method == "POST":
        args += ["-X", "POST", "-H", "Content-Type: application/json",
                 "-d", json.dumps(body, ensure_ascii=False)]

    gap = MIN_INTERVAL - (time.time() - _last_call[0])
    if gap > 0:
        time.sleep(gap)
    _last_call[0] = time.time()

    out = curl([*args, url])
    try:
        d = json.loads(out)
    except json.JSONDecodeError:
        die(f"응답 파싱 실패 ({path}): {out[:300]}")

    # HTTP 200 이어도 실패일 수 있다 — resultType 이 진실이다.
    if d.get("resultType") == "SUCCESS":
        return d["success"]

    err = d.get("error") or {}
    et, code = err.get("errorType"), err.get("errorCode", "")
    reason = err.get("reason", "")

    if code == "IP_NOT_ALLOWED":
        die(f"출발지 IP 미등록. 현재 나가는 IP = {egress_ip()}\n"
            f"  쉐어링크 어드민 > API 연동 에서 이 IP 를 등록해 주세요.")
    if et == 401 and _try == 0:
        return call(env, path, get_token(env, force=True), method, params, body, _try + 1)
    if et in (429, 500) and _try < 3:
        wait = 2 ** _try
        try:  # 429 는 서버가 알려준 대기 시간을 우선한다
            hdr = open("/tmp/.toss_hdr").read()
            for line in hdr.splitlines():
                if line.lower().startswith("retry-after:"):
                    wait = float(line.split(":", 1)[1].strip())
        except Exception:
            pass
        print(f"  {et} — {wait}초 후 재시도 ({_try + 1}/3)", file=sys.stderr)
        time.sleep(wait)
        return call(env, path, token, method, params, body, _try + 1)

    die(f"{et} {code}: {reason}")


# ───────────────────────── 출력 ─────────────────────────

def show(items):
    if not items:
        print("  (없음)")
        return
    print(f'{"tacaItemId":>12} {"가격":>9} {"정가":>9} {"할인":>5} {"평점":>5} {"후기":>7}  상품명')
    print("─" * 100)
    for i in items:
        so = " [품절]" if i.get("isSoldOut") else ""
        print(f'{i.get("tacaItemId",""):>12} {i.get("displayPrice",0):>9,} '
              f'{i.get("originalPrice",0) or 0:>9,} {str(i.get("discountRate","")) + "%":>5} '
              f'{i.get("reviewScore","") or "-":>5} {i.get("reviewCount",0) or 0:>7,}  '
              f'{(i.get("displayName") or "")[:38]}{so}')


# ───────────────────────── 명령 ─────────────────────────

def cmd_refresh(env, token, path):
    """저장해 둔 상품의 최신 가격·품절 여부를 확인한다.

    가격은 자주 바뀐다(파우시가 한 주에 34,920 → 28,570 으로 바뀌었다).
    글에 박아둔 숫자가 언제 틀렸는지를 사람이 눈으로 잡을 수는 없다.
    """
    p = path if os.path.isabs(path) else os.path.join(ROOT, path)
    d = json.load(open(p, encoding="utf-8"))
    targets = [(i, i.get("taca_item_id")) for i in d.get("items", [])
               if i.get("platform") == "toss" and i.get("taca_item_id")]
    if not targets:
        die("갱신할 토스 상품이 없습니다. items[].taca_item_id 를 채워 주세요.")

    ids = ",".join(str(t[1]) for t in targets[:30])
    res = call(env, "/products/detail", token, params={"tacaItemIds": ids})
    by_id = {x["tacaItemId"]: x for x in res.get("items", [])}

    changed = []
    for item, tid in targets:
        cur = by_id.get(tid)
        if not cur:
            print(f'  ? {item["name"][:34]} — 조회 안 됨')
            continue
        old, new = item.get("price"), cur["displayPrice"]
        flag = "품절" if cur.get("isSoldOut") else ""
        if old != new:
            changed.append((item["name"], old, new))
            item["price"] = new
            if cur.get("originalPrice"):
                item["list_price"] = cur["originalPrice"]
        item["sold_out"] = bool(cur.get("isSoldOut"))
        mark = "→" if old != new else " "
        print(f'  {mark} {item["name"][:34]:36s} {old:>8,} {mark} {new:>8,} {flag}')

    if changed:
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n{len(changed)}건 갱신 — {path} 저장. 글을 다시 생성하세요.")
    else:
        print("\n변동 없음.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["health", "whoami", "best", "categories",
                                    "category-best", "deals", "detail", "link", "refresh"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--alpha", action="store_true", help="알파(테스트) 환경")
    ap.add_argument("--size", type=int, default=20)
    ap.add_argument("--cursor")
    a = ap.parse_args()
    env = "alpha" if a.alpha else "prod"

    if a.cmd == "whoami":
        print(f"출발지 IP: {egress_ip()}")
        print("  이 IP 를 쉐어링크 어드민 > API 연동 에 등록해야 호출이 허용됩니다.")
        print("  ⚠ 컨테이너가 재생성되면 바뀔 수 있으니 호출 전 매번 확인하세요.")
        return

    token = get_token(env)

    if a.cmd == "health":
        print(json.dumps(call(env, "/health", token), ensure_ascii=False))
        print(f"✓ 인증·IP·라우팅 정상 ({env}) · 출발지 {egress_ip()}")
    elif a.cmd == "categories":
        print(json.dumps(call(env, "/categories", token), ensure_ascii=False, indent=2)[:3000])
    elif a.cmd == "best":
        p = {"size": a.size}
        if a.cursor:
            p["cursor"] = a.cursor
        r = call(env, "/products/best-selling", token, params=p)
        show(r.get("items", []))
        if r.get("hasNext"):
            print(f'\n다음 페이지: --cursor {r["nextCursor"]}')
    elif a.cmd == "category-best":
        if not a.arg:
            die("categoryId 가 필요합니다")
        r = call(env, "/products", token, params={"categoryId": a.arg, "size": a.size})
        show(r.get("items", []))
    elif a.cmd == "deals":
        r = call(env, "/products/today-deals", token, params={"size": a.size})
        show(r.get("items", []))
    elif a.cmd == "detail":
        if not a.arg:
            die("tacaItemIds 가 필요합니다 (콤마 구분, 최대 30)")
        r = call(env, "/products/detail", token, params={"tacaItemIds": a.arg})
        show(r.get("items", []))
        if r.get("notFoundIds"):
            print("조회 안 됨:", r["notFoundIds"])
    elif a.cmd == "link":
        pub = os.environ.get("TOSS_PUBLISHER_ID")
        if not pub:
            die("TOSS_PUBLISHER_ID 환경변수가 없습니다 (퍼블리셔 UUID)")
        if not a.arg:
            die("tacaItemId 가 필요합니다")
        r = call(env, "/links", token, method="POST",
                 body={"tacaItemId": int(a.arg), "publisherId": pub})
        print(json.dumps(r, ensure_ascii=False, indent=2))
        print("\n⚠ 수익은 이 링크로만 집계됩니다. productUrl 은 추적되지 않습니다.")
    elif a.cmd == "refresh":
        cmd_refresh(env, token, a.arg or "posts_data/feeder.json")


if __name__ == "__main__":
    main()
