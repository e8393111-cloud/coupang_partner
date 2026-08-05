# 블로거 자동 발행 연동

`tools/publish_blogger.py` 를 쓰기 위한 준비. **한 번만 하면 되고, 폰만으로 됩니다.**

---

## 왜 필요한가

지금은 페이지를 생성해도 사람이 블로거 편집기에 붙여넣어야 합니다.
하루 몇 번 갱신하는 특가 페이지에서 그건 자동화가 아니라 그냥 수동입니다.

이 연동은 **토스 IP 제한과 무관**합니다. 구글은 출발지 IP를 보지 않습니다.
그래서 토스 쪽이 어떻게 풀리든 이건 그대로 쓰입니다.

---

## 1. 구글 클라우드에서 OAuth 클라이언트 만들기

`console.cloud.google.com` 에서 (폰 브라우저로도 됩니다):

1. 프로젝트 만들기 (이름 아무거나)
2. **API 및 서비스 > 라이브러리** → `Blogger API v3` 검색 → **사용 설정**
3. **OAuth 동의 화면** → 외부 → 앱 이름·이메일만 채우고 저장
   - 테스트 사용자에 **본인 이메일 추가** (게시 안 해도 됩니다)
4. **사용자 인증 정보 > 사용자 인증 정보 만들기 > OAuth 클라이언트 ID**
   - 애플리케이션 유형: **데스크톱 앱**
   - **클라이언트 ID** 와 **클라이언트 보안 비밀**을 받습니다

## 2. 리프레시 토큰 받기

```bash
export BLOGGER_CLIENT_ID="...apps.googleusercontent.com"
export BLOGGER_CLIENT_SECRET="..."

python3 tools/publish_blogger.py authurl
```

출력된 주소를 브라우저에서 열고 승인합니다.
승인하면 `http://localhost/?code=...` 로 넘어가면서 **"사이트에 연결할 수 없음"** 이 뜹니다.
**정상입니다.** 주소창의 `code=` 뒤 값을 복사하세요.

```bash
python3 tools/publish_blogger.py exchange "복사한_code"
```

`BLOGGER_REFRESH_TOKEN=...` 이 출력됩니다.

> ⏱ **code 는 1회용이고 몇 분 만에 만료됩니다.** 실패하면 `authurl` 부터 다시 하면 됩니다.

## 3. 환경변수로 보관

```bash
export BLOGGER_CLIENT_ID="..."
export BLOGGER_CLIENT_SECRET="..."
export BLOGGER_REFRESH_TOKEN="..."
```

🔴 **이 repo 는 공개입니다. 파일에 쓰지 마세요.**
노출됐다면 구글 계정 > 보안 > 서드파티 액세스 에서 취소하고 다시 받으면 됩니다.
리프레시 토큰은 취소 전까지 유효합니다.

---

## 쓰는 법

```bash
python3 tools/publish_blogger.py pages                 # pageId 확인
python3 tools/publish_blogger.py update <pageId> blog/deals/today.html
python3 tools/publish_blogger.py post blog/deals/weekly.html \
        --title "이번 주 가장 쌌던 것" --labels "주간,특가" --draft
```

`pages` 가 찍어주는 pageId 는 `deals_data/blog.json` 에 받아 적어뒀습니다.

```
오늘의특가   5948420653045379325   /p/today.html      ← 갱신 대상
연락처       8483867241106284492
개인정보     7241110962036182937
소개          360711182009705771
blogId       6692048625594636316
```

**연동 확인 완료 2026-08-05** — 조회·쓰기 모두 실제 페이지에 반영되는 것까지 봤습니다.

---

## 반드시 지킬 것

**새 페이지를 만들지 말고 기존 페이지를 갱신(`update`)하세요.**
블로거 페이지 주소는 첫 발행 때 고정되고 이후 못 바꿉니다. 「오늘의 특가」가
`/p/today.html` 을 유지해야 북마크와 재방문이 삽니다. 새로 만들면 주소가
`today_1.html` 처럼 밀립니다.

**주간 아카이브만 `post` 로 새 글을 씁니다.** 그건 쌓이는 게 목적입니다.

**`--draft` 로 먼저 확인하세요.** 특히 첫 발행 때. 초안으로 올려 눈으로 보고
블로거에서 게시하면 됩니다.
