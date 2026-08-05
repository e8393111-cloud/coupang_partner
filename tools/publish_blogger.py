#!/usr/bin/env python3
"""블로거(Blogspot) 발행 클라이언트.

    export BLOGGER_CLIENT_ID=...  BLOGGER_CLIENT_SECRET=...  BLOGGER_REFRESH_TOKEN=...
    python3 tools/publish_blogger.py pages  --blog oneulmandeal.blogspot.com
    python3 tools/publish_blogger.py update <pageId> blog/deals/today.html
    python3 tools/publish_blogger.py post   blog/deals/weekly.html --title "이번 주 가장 쌌던 것"
    python3 tools/publish_blogger.py backup --blog eodisanow.blogspot.com

토큰이 없다면 (폰만으로도 됩니다):
    python3 tools/publish_blogger.py authurl      # 이 주소를 폰 브라우저에서 열고 승인
    python3 tools/publish_blogger.py exchange <code>

🔴 키를 파일에 쓰지 마세요. 이 repo 는 공개입니다. 환경변수로만 넘깁니다.

설계 근거:
- 페이지 주소는 첫 발행 때 고정되고 이후 못 바꾼다 → **새로 만들지 않고 기존 페이지를
  갱신(PATCH)한다.** 「오늘의 특가」가 /p/today.html 을 계속 유지해야 북마크가 산다.
- 갱신은 pageId 로 한다. 제목·주소가 바뀌어도 ID 는 그대로다.
- 구글 액세스 토큰은 1시간짜리라 캐시하지 않는다. 리프레시 토큰만 오래 산다.
"""
import argparse
import json
import os
import subprocess
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://www.googleapis.com/blogger/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
SCOPE = "https://www.googleapis.com/auth/blogger"
# 데스크톱 클라이언트의 표준 리다이렉트. 폰에서 열면 "연결할 수 없음" 이 뜨지만
# 주소창에 ?code=... 가 남는다 — 그걸 복사해 exchange 에 넣으면 된다.
REDIRECT = "http://localhost"


def die(msg):
    raise SystemExit(f"✗ {msg}")


def curl(args, timeout=40):
    r = subprocess.run(["curl", "-sS", "--max-time", str(timeout), *args],
                       capture_output=True, text=True)
    if r.returncode:
        die(f"네트워크 오류: {r.stderr.strip()[:200]}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        die(f"응답 파싱 실패: {r.stdout[:300]}")


def need(name):
    v = os.environ.get(name)
    if not v:
        die(f"{name} 환경변수가 없습니다")
    return v


def access_token():
    d = curl(["-X", "POST", TOKEN_URL, "-d", urllib.parse.urlencode({
        "client_id": need("BLOGGER_CLIENT_ID"),
        "client_secret": need("BLOGGER_CLIENT_SECRET"),
        "refresh_token": need("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token"})])
    if "access_token" not in d:
        die(f"토큰 갱신 실패: {json.dumps(d, ensure_ascii=False)[:300]}\n"
            f"  리프레시 토큰이 만료·취소됐을 수 있습니다. authurl 부터 다시 하세요.")
    return d["access_token"]


def api(path, token, method="GET", body=None, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    args = ["-H", f"Authorization: Bearer {token}"]
    if method != "GET":
        args += ["-X", method, "-H", "Content-Type: application/json",
                 "-d", json.dumps(body or {}, ensure_ascii=False)]
    d = curl([*args, url])
    if "error" in d:
        e = d["error"]
        die(f'{e.get("code")} {e.get("message")}')
    return d


def blog_id(token, blog):
    """blogId 를 직접 받거나 주소로 찾는다."""
    if blog.isdigit():
        return blog
    if not blog.startswith("http"):
        blog = "https://" + blog
    return api("/blogs/byurl", token, params={"url": blog})["id"]


def read_html(path):
    p = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.exists(p):
        die(f"파일이 없습니다: {path}")
    return open(p, encoding="utf-8").read()


def fetch_all(bid, token, kind):
    """posts / pages 전체를 페이지네이션 끝까지 가져온다."""
    out, tok = [], None
    while True:
        p = {"maxResults": 50, "fetchBodies": "true", "status": ["live", "draft"]}
        if tok:
            p["pageToken"] = tok
        r = api(f"/blogs/{bid}/{kind}", token, params=p)
        out += r.get("items", [])
        tok = r.get("nextPageToken")
        if not tok:
            return out


def cmd_backup(bid, token, blog, outdir):
    """글·페이지를 레포에 받아둔다.

    블로거 자체 백업(XML)은 사람이 읽기 어렵고 받은 기기에만 남는다. 레포는
    깃허브에 있어서 블로그가 잠겨도 같이 사라지지 않고, 변경 이력도 남는다.
    ⚠️ 이미지는 구글 포토에 따로 저장돼 본문에는 주소만 있다 — 여기에도 안 담긴다.
    """
    root = os.path.join(ROOT, outdir, blog.split(".")[0])
    n = {}
    for kind in ("posts", "pages"):
        items = fetch_all(bid, token, kind)
        d = os.path.join(root, kind)
        os.makedirs(d, exist_ok=True)
        for it in items:
            # 초안은 url 이 블로그 루트라 슬러그가 안 나온다 → id 로 떨어뜨린다
            url = it.get("url", "")
            slug = url.rstrip("/").split("/")[-1] if url.endswith(".html") else ""
            slug = (slug or f'{it.get("status", "draft").lower()}-{it["id"]}').replace(".html", "")
            with open(os.path.join(d, f"{slug}.html"), "w", encoding="utf-8") as f:
                f.write(f'<!-- {it.get("title","")} · {it.get("published","")} · '
                        f'{it.get("url","")} -->\n{it.get("content","")}\n')
        # 본문을 뺀 목록은 따로 남긴다 — 무엇이 있었는지 한눈에 보려고
        with open(os.path.join(root, f"{kind}.json"), "w", encoding="utf-8") as f:
            json.dump([{k: v for k, v in i.items() if k != "content"} for i in items],
                      f, ensure_ascii=False, indent=2)
        n[kind] = len(items)
    print(f'백업: {os.path.relpath(root, ROOT)} · 글 {n["posts"]}개 · 페이지 {n["pages"]}개')
    print("⚠️ 이미지는 포함되지 않습니다 (구글 포토에 별도 저장됨)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["authurl", "exchange", "pages", "update", "post", "backup"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("arg2", nargs="?")
    ap.add_argument("--blog", default=os.environ.get("BLOGGER_BLOG", "oneulmandeal.blogspot.com"))
    ap.add_argument("--title")
    ap.add_argument("--labels", default="")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--out", default="blog/backup", help="backup 저장 위치")
    a = ap.parse_args()

    if a.cmd == "authurl":
        q = urllib.parse.urlencode({
            "client_id": need("BLOGGER_CLIENT_ID"), "redirect_uri": REDIRECT,
            "response_type": "code", "scope": SCOPE,
            "access_type": "offline", "prompt": "consent"})
        print(f"{AUTH_URL}?{q}\n")
        print("이 주소를 브라우저에서 열고 승인하세요.")
        print("승인 후 '연결할 수 없음' 페이지로 넘어가는데, 주소창의 code= 뒤 값이 필요합니다.")
        print("  python3 tools/publish_blogger.py exchange <code>")
        return

    if a.cmd == "exchange":
        if not a.arg:
            die("code 가 필요합니다")
        d = curl(["-X", "POST", TOKEN_URL, "-d", urllib.parse.urlencode({
            "client_id": need("BLOGGER_CLIENT_ID"),
            "client_secret": need("BLOGGER_CLIENT_SECRET"),
            "code": urllib.parse.unquote(a.arg),
            "grant_type": "authorization_code", "redirect_uri": REDIRECT})])
        if "refresh_token" not in d:
            die(f"교환 실패: {json.dumps(d, ensure_ascii=False)[:300]}\n"
                f"  code 는 1회용이고 몇 분 안에 만료됩니다. authurl 부터 다시 하세요.")
        print(f'\nBLOGGER_REFRESH_TOKEN={d["refresh_token"]}\n')
        print("이 값을 환경변수로 저장하세요. 파일에 쓰거나 커밋하지 마세요 (이 repo 는 공개입니다).")
        print("실수로 노출됐다면 구글 계정 > 보안 > 서드파티 액세스 에서 취소하고 다시 받으면 됩니다.")
        return

    # 인자 검사를 네트워크보다 먼저 한다. 사용법을 틀렸을 뿐인데 토큰부터
    # 받으러 가면, 진짜 원인 대신 인증 오류가 보인다.
    if a.cmd == "update" and not (a.arg and a.arg2):
        die("사용법: update <pageId> <htmlfile>")
    if a.cmd == "post":
        if not a.arg:
            die('사용법: post <htmlfile> --title "제목"')
        if not a.title:
            die("--title 이 필요합니다")
    html = read_html(a.arg2 if a.cmd == "update" else a.arg) if a.cmd in ("update", "post") else ""

    token = access_token()
    bid = blog_id(token, a.blog)

    if a.cmd == "backup":
        cmd_backup(bid, token, a.blog, a.out)
        return

    if a.cmd == "pages":
        r = api(f"/blogs/{bid}/pages", token, params={"fetchBodies": "false"})
        print(f'블로그 {a.blog} (id {bid})\n')
        print(f'{"pageId":>20}  {"상태":<9} 제목 / 주소')
        for p in r.get("items", []):
            print(f'{p["id"]:>20}  {p.get("status",""):<9} {p.get("title","")}')
            print(f'{"":>20}  {"":<9} {p.get("url","")}')
        return

    if a.cmd == "update":
        body = {"content": html}
        if a.title:
            body["title"] = a.title
        r = api(f"/blogs/{bid}/pages/{a.arg}", token, method="PATCH", body=body)
        print(f'갱신: {r.get("title")} ({len(html):,}자)\n{r.get("url")}')
        return

    if a.cmd == "post":
        body = {"title": a.title, "content": html}
        if a.labels:
            body["labels"] = [x.strip() for x in a.labels.split(",") if x.strip()]
        r = api(f"/blogs/{bid}/posts", token, method="POST", body=body,
                params={"isDraft": "true" if a.draft else "false"})
        print(f'발행: {r.get("title")} ({len(html):,}자)\n{r.get("url")}')
        return


if __name__ == "__main__":
    main()
