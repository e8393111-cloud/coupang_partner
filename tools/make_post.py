#!/usr/bin/env python3
"""업로드 키트 생성기 — 플랫폼별 캡션을 바로 복붙할 수 있게 뽑아준다.

products/<id>.json 의 "post" 블록 → posts/<id>.md

공정위 문구는 **항상 캡션 맨 앞**에 박힌다("더보기"로 잘리면 위험).
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."


def caption(hook, post, link, tag_count):
    tags = " ".join(post["hashtags"][:tag_count])
    return "\n".join([
        DISCLOSURE,
        "",
        hook,
        post["body"],
        post["cta"] if not link else f"👉 {link}",
        "",
        tags,
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--link", default="", help="캡션에 직접 넣을 링크(유튜브 쇼츠 등). 없으면 '프로필 링크' 문구 사용")
    args = ap.parse_args()

    cfg_path = args.config if os.path.isabs(args.config) else os.path.join(ROOT, args.config)
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    post, name = cfg["post"], cfg.get("name", cfg["id"])
    hooks = post["hooks"]

    out = [
        f"# 업로드 키트 — {name}",
        "",
        "> 자동 생성: `python3 tools/make_post.py products/%s.json`" % cfg["id"],
        "> 공정위 문구는 **캡션 맨 앞**에 그대로 둘 것 (더보기로 잘리면 미노출 위험).",
        "",
        "## 영상",
        f"- 파일: `{cfg['out']}`",
        "- 틱톡은 앱에서 트렌딩 사운드를 얹어 재업로드(무음 시청 대비 자막은 이미 번인됨)",
        "",
        "## 훅 A/B (썸네일·첫 3초 문구)",
    ]
    for label, h in zip("ABC", hooks):
        out.append(f"- **{label}** {h}")
    out += ["", "## 캡션 — 인스타 릴스", "```", caption(hooks[0], post, args.link, 6), "```",
            "", "## 캡션 — 틱톡 (해시태그 3~4개)", "```", caption(hooks[1], post, args.link, 4), "```",
            "", "## 캡션 — 유튜브 쇼츠", "```", caption(hooks[2], post, args.link, 6), "```",
            "", "## 업로드 체크리스트",
            "- [ ] 공정위 문구: 영상 상단 바 + 캡션 맨 앞 + 랜딩 상단 (3곳 다)",
            "- [ ] 프로필 바이오 링크 = 랜딩/인포크링크 (틱톡은 비즈니스 계정이어야 링크 생김)",
            "- [ ] 랜딩 구매 버튼에 쿠파스 딥링크가 실제로 박혔는지",
            "- [ ] 가격/재고가 쿠팡 실제 페이지와 일치하는지",
            ""]

    out_path = os.path.join(ROOT, "posts", f"{cfg['id']}.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("생성:", out_path)


if __name__ == "__main__":
    main()
