# 🚀 쿠팡 파트너스 수익화 프로젝트 — 핸드오프 (이어서 작업용)

> 마지막 업데이트: 2026-07-29 · 다른 세션에서 이 파일 읽고 그대로 이어가면 됨.

## 0. 한 줄 요약
**트랙이 둘이다.**
1. **숏폼 트랙** — 쿠팡 파트너스 릴스/쇼츠/틱톡. 첫 상품(UV 모기퇴치기) 완성 영상 + 상세페이지까지 제작 완료.
2. **블로그 트랙** — 블로그스팟 「어디사」(`eodisanow`, 반려동물 가전 가격비교). 2026-07-29 개설, 필수 페이지 3개 발행 완료,
   **첫 글 발행 완료** (`/2026/07/auto-pet-feeder.html`).
3. **특가 트랙** — 블로그스팟 「오늘만」(`oneulmandeal`, 토스 하루특가 자동 갱신).
   2026-08-04 개설. 리뷰 블로그와 **의도적으로 분리** — 자동 발행물이
   리뷰 글 신뢰를 깎지 않도록. 설계는 `blog/deals_plan.md`.

두 트랙 모두 **설정(JSON) 하나 채우면 결과물이 나오는** 파이프라인으로 정리돼 있다.
전략·근거는 `PLAN.md`, 실행 방법은 이 파일.

## 0-1. ⚠️ 브랜치 상태 (먼저 읽을 것)
- `claude/coupang-partners-monetization-v92w7y` 와 `claude/coupang-partners-monetization-3xx5n7` **두 브랜치는 내용이 같다**(2026-07-29 미러링). 어느 쪽 raw/Pages URL 을 써도 동일.
- 앞으로도 커밋할 때마다 **두 브랜치에 같이 push** 할 것 (기존에 공유한 v92w7y URL 이 계속 살아 있어야 함).
- (별개 실험 브랜치 `claude/kupas-monetization-7gk3tl` 에 파이썬 에이전트 파이프라인이 따로 있음. 이 핸드오프와는 무관.)

---

## 1. 확정된 전략 (사용자 결정)
- **페이스리스** (얼굴/손 노출 X, 직접 촬영 X, 제품 구매 X)
- footage는 **소싱**: ① 리얼 raw 제품클립(알리익스프레스·더우인·샤오홍슈) 짜집기, 또는 ② **Mirra**(AI 광고 생성)로 초벌 뽑기
- 저작권: 경고 수준 관리 감수. **단, 남의 "완성 영상" 재업 금지** → raw 제품 클립만.
- 목표: 퀵윈(볼륨) 먼저 → 터진 패턴을 시스템(Skill)으로 고정
- AI(나)는 **footage 빼고 전부** 담당(리서치·카피·편집·자막·더빙·상세페이지)

## 2. 핵심 학습 (중요 — 반복 실수 방지)
- ❌ **higgsfield AI b-roll은 전환 약함** (예쁜 광고티, 진짜 시연 증거 없음). 리얼 footage나 Mirra가 나음.
- ✅ **Mirra 초벌 + 내 ffmpeg 후처리** 조합이 "막 뽑기"에 제일 실용적.
- 제품 본질: **거실 구석/베란다/캠핑에 사람과 떨어뜨려 두고 씀** (침실 머리맡 아님! UV가 밝음). 캠핑은 롤테이블/랜턴스탠드 (나뭇가지 X).
- VO 톤: **Hana 보이스 + 홈쇼핑 쇼호스트 톤** 채택. qwen speech_rate가 잘 안 먹음 → **속도는 렌더 때 ffmpeg atempo로** 조정(`vo_atempo`).
- TTS에서 **"끝" 글자 깨짐**(끕) → 우회 표현 사용.
- 공정위 문구 **필수**: 영상 내(상단 바) + 캡션 맨앞 + 인포크링크/상세페이지 상단. (캡션만은 위험 — "더보기"로 잘림)
- 자막 폰트에 **이모지 없음** → 영상 자막엔 이모지 쓰지 말 것 (캡션·상세페이지는 OK).

## 3. 환경 제약 (반드시 인지)
- **egress 차단**: 쿠팡/쇼핑몰 **다운로드 불가**(403), higgsfield 스토리지 **업로드 불가**.
  ~~cloudfront 다운로드 불가~~ → **틀린 기록이었다. cloudfront 는 받아진다** (아래 §3 파일 다리 항목 참고).
- ✅ **단, `curl` 은 WebFetch 보다 많이 통과한다** (2026-07-29 확인): 네이버 블로그·티스토리·토스 문서 정상 수신. WebSearch 툴도 동작.
  **쿠팡 본체(`www.coupang.com`)와 `shopping.toss.im` 은 curl 로도 403** → 가격·재고 확인은 여전히 사용자 몫.
- ❌ **브라우저(Chromium/Playwright)는 쓸 수 없다** (2026-07-29 정밀 진단 완료):

  | 테스트 | 결과 |
  |---|---|
  | Chromium 실행 + 로컬 서버 로드 | ✅ 정상 (브라우저 자체는 멀쩡) |
  | `--proxy-server` 플래그 동작 | ✅ CONNECT 가 상류로 전달됨 |
  | **curl** → 중계기 → 정책 프록시 | ✅ **200** |
  | **Chromium** → 같은 중계기 → 정책 프록시 | ❌ **ERR_CONNECTION_CLOSED** |

  브라우저도, 프록시 설정도, 경로도 정상인데 **정책 프록시가 크로미움의 터널만 끊는다**
  (프록시는 이걸 실패로 기록조차 하지 않는다). TLS 검증 비활성화·우회는 금지 사항이라 시도하지 않았다.
  → **JS 렌더링이 필요한 사이트(토스쇼핑·쿠팡)는 이 세션에서 방법이 없다. 다시 시도하지 말 것.**
  → 대신 **사용자의 크롬 확장 클로드**가 그 역할을 한다. `blog/collect_prompt.md` 참고.
- ✅ **토스쇼핑 쉐어링크 Open API 출시** (2026-08-04 확인). 지금까지 사용자 몫이던
  가격·품절 확인과 링크 발급이 서버 연동으로 가능해졌다.
  - 문서: `sharelink-docs.toss.im` — **내 환경에서 열린다.** GitBook 이라
    모든 페이지에 `.md` 를 붙이면 마크다운, `/llms.txt` 에 전체 색인.
    `?ask=<질문>` 으로 문서 질의도 된다.
  - Base URL: 운영 `https://sharelink.toss.im/openapi` · 알파 `https://alpha-sharelink.toss.im/openapi`
  - 토큰: `POST https://oauth2.cert.toss.im/token` (client_credentials, 유효기간 약 1년)
  - 엔드포인트: 카테고리 / 카테고리 베스트 / 베스트 / 하루특가 /
    **상품 상세(최신 가격·품절 여부, 최대 30건)** / **쉐어링크 발급**
  - 스코프: `sharelink:read` (조회) · `sharelink:write` (링크 발급)
  - ⚠️ **수익은 이 API 로 발급한 링크로만 집계된다.** 조회 응답의 `productUrl` 은 추적 안 됨.
  - ⚠️ **출발지 IP 등록 필수.** 미등록 IP 는 `IP_NOT_ALLOWED` 로 전부 차단.
    이 세션의 egress = `160.79.106.100` (3회 연속 동일). 다만 **컨테이너가
    재생성되면 바뀔 수 있으므로 고정 IP 로 신뢰하면 안 된다.** 호출 전 매번 확인할 것.
  - 🔴 **Access Key / Secret Key 를 repo 에 넣지 말 것.** 이 repo 는 공개다.
    환경변수로만 주입한다. Secret 은 발급 직후 1회만 표시되고, 재발급하면
    같은 사업자의 기존 키가 즉시 무효가 된다.
- ❌ **중국 플랫폼 3곳 전부 로그인 게이트** (2026-07-29 확인, 재시도 금지):

  | 사이트 | 결과 |
  |---|---|
  | `xiaohongshu.com` 검색 | HTTP 200 · 724KB 오지만 `__INITIAL_STATE__` 에 **결과 0건** (로그인 API 별도 호출) |
  | 샤오홍수 개별 노트 | `HOME_FEED_LAYOUT_PLACEHOLDER` 만 — 본문 렌더 안 됨 |
  | `s.taobao.com` 검색 | 셸만 33KB, 상품 데이터 없음 · 로그인 유도 |
  | `s.1688.com` 검색 | 5KB 셸 |

  서명 헤더(`X-s`/`X-t`) + 세션이 필요한 구조. 우회는 시도하지 않는다.
- ✅ **`thumbnail*.coupangcdn.com` 은 도달 가능** (2026-07-29 발견): 가짜 경로에 **404** 응답
  = 호스트는 열려 있다는 뜻. `www.coupang.com`(403)·`image6`·`static`(403)과 다르다.
  → **영상/이미지 소재는 사용자가 상세페이지에서 "동영상 주소 복사" 해주면 내가 받을 수 있다.**
  m3u8 도 가능. 브라우저는 사용자, CDN 은 나 — 되는 구간을 나눠 쓴다.
- ❌ **Blogger 커넥터 없음** → 블로그 직접 수정 불가. 자동 발행은 **Make 경유**가 유일한 실용 경로
  (Make 에 네이티브 Blogger 앱 확인: Create/Update/Publish a post. 단 **페이지(Page) 생성 모듈은 없음** → 필수 페이지는 수동).
  blogId = `5230656979093557379`. googleapis.com 자체는 도달 가능(403=인증없음, 차단 아님)이나
  OAuth 토큰을 세션에 넘기는 방식은 권장하지 않는다.
- **우회 = 공개 GitHub repo가 "파일 다리"**:
  - 내가 만든 것 → repo push → 사용자는 `raw.githubusercontent.com/.../<branch>/...` 로 봄
  - 사용자가 준 파일(footage, vo.mp3) → repo 업로드 → 내가 `git pull`로 가져와 편집
  - ✅ **higgsfield 생성물은 내가 직접 받을 수 있다** (2026-07-29 실측, 이전 기록은 틀렸다):
    ```
    GET https://d8j0ntlcm91z4.cloudfront.net/.../hf_20260724_015736_….png
    → HTTP 200 · 6,225,704B · image/png · 매직바이트 \x89PNG 정상
    ```
    생성물을 못 받으면 concat·렌더가 불가능하므로 이건 기능의 존폐를 가르는 사실이다.
    **단, cloudfront URL 은 만료될 수 있다** → 생성 직후 바로 받아서 repo 에 커밋할 것.
  - 사진을 higgsfield 로 넣을 때는 **업로드하지 말고** repo 다리를 쓴다:
    repo commit → `raw.githubusercontent.com/...` → `media_import_url` → media_id.
    (`upload.higgsfield.ai` 는 403. `medias[].value` 는 media_id/job_id 만 받고 URL 은 안 받는다.)
- repo는 **공개(public)** 상태 (Pages·raw URL 위해)
- 세션 시작할 때마다 설치 필요: `pip install imageio-ffmpeg Pillow`
  - ffmpeg 7.0.2 static (libx264 O, **drawtext 없음** → 자막은 PIL로 PNG 그려 overlay)
  - 한글 폰트 = `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`

## 4. repo 구조
```
HANDOFF.md                     # ← 이 파일 (실행 방법)
PLAN.md                        # 전략·근거·의사결정 기록
index.html / manifest.json     # 수익화 대시보드(별개 툴, PWA)

─── 숏폼 트랙 ───────────────────────────────
products/
  _template.json               # 새 상품 시작점
  mosquito.json                # 모기퇴치기 전체 설정
tools/
  prep_source.py               # ① 소스 크롭/트림/이어붙이기
  render_short.py              # ② VO 합성 + 공정위 상단바 + 자막 번인
  make_landing.py              # ③ 상세페이지 생성
  landing_template.html        #    └ 상세페이지 템플릿
  make_post.py                 # ④ 업로드 캡션 키트
  plumbing_test.py             # ffmpeg+한글자막 배관 테스트
assets/  vo.mp3  p/mosquito.html  posts/mosquito.md

─── 블로그 트랙 ─────────────────────────────
posts_data/
  feeder.json                  # ★자동급식기 글 데이터(상품·후기·링크·배너)
  _sample.json                 # 스키마 예시
tools/
  make_blogpost.py             # ★글 생성기 (문구·표·논리)
  blogpost_template.html       #    └ 레이아웃·CSS (디자인은 여기서)
  make_preview.py              # 발행 전 미리보기 (폰트 인라인)
  danawa_specs.py              # 다나와에서 후보·모델명·사양 수집
blog/
  README.md                    # 블로그 운영 메모
  collect_prompt.md            # 브라우저 클로드용 상품 수집 프롬프트
  pages/about|privacy|contact.html   # 필수 페이지 3종 (발행 완료)
  posts/자동급식기.html          # ★첫 글 (생성물)
assets/fonts/sub-*.woff2       # Pretendard 서브셋 (미리보기용, OFL 1.1)
```
> `blog/posts/*.html`, `p/*.html`, `posts/*.md`, `assets/*final*.mp4` 는 **생성물**이다.
> 고칠 땐 `posts_data/` · `products/` 의 JSON 이나 `tools/*template*` 을 고치고 다시 생성할 것.

## 5. 완성물 URL
- **최종 영상**: `https://raw.githubusercontent.com/e8393111-cloud/coupang_partner/claude/coupang-partners-monetization-v92w7y/assets/mirra_final.mp4`
- **상세페이지**(Pages 켜지면): `https://e8393111-cloud.github.io/coupang_partner/p/mosquito.html`
- 대시보드 아티팩트: `https://claude.ai/code/artifact/d6464cf6-1dfb-4b75-b94a-7081359c59e3`

## 6. 작동하는 파이프라인 (반자동)
```
[상품 리서치·훅·스크립트]  ← 나
        ↓
[Mirra 초벌 뽑기 / raw 클립 소싱]  ← 사용자   → repo 업로드 (footage/)
        ↓
① python3 tools/prep_source.py   products/<id>.json   # 크롭·트림·concat
        ↓
[VO 생성: 한국어 홈쇼핑 TTS]  ← higgsfield generate_audio (세팅 아래)
        ↓  사용자가 vo_<id>.mp3 repo 업로드
② python3 tools/render_short.py  products/<id>.json   # VO 1.5x + 공정위 + 자막
③ python3 tools/make_landing.py  products/<id>.json   # 상세페이지
④ python3 tools/make_post.py     products/<id>.json   # 업로드 캡션 키트
        ↓
push → 사용자 다운로드 → 틱톡/릴스 업로드
```

### 자막 타이밍 잡는 법
```
python3 tools/render_short.py products/<id>.json --probe       # VO 말하는 구간 출력
python3 tools/render_short.py products/<id>.json --auto-caps   # 무음 기준 자동 배분
```
`--probe` 로 나온 구간 경계를 보고 JSON `captions` 의 `start`/`end` 를 손보는 게 제일 정확하다.
(`--auto-caps` 는 초벌용. 모기퇴치기 기준 수동값과 거의 같지만 한 군데가 뭉쳤다.)

### VO(TTS) 재사용 세팅 (higgsfield generate_audio)
- model: `qwen_audio_tts`, language: `ko`
- voice: **Hana** — voice_type `preset`, voice_id `c25f78a0-714e-42af-8da3-a399cef94968`
- instruction(홈쇼핑): "홈쇼핑 쇼호스트처럼 열정적이고 친근하게 설득하듯, 뚝뚝 끊지 말고 부드럽게 이어서, 자연스럽게 흐르듯이, 활기차게"
- speech_rate 1.15~1.3 (효과 적음), pitch_rate 1.03. **실제 속도는 렌더 때 `vo_atempo`(기본 1.5)로.**
- ⚠️ "끝" 등 일부 글자 깨짐 → 대본에서 회피.
- 📏 **대본 길이 예산 (2026-08-04 실측): 한국어 TTS 는 약 4.05자/초.**
  `대본 글자수 = 영상초 × atempo × 4.05`
  파우시에서 219자를 쓴 결과 VO 54초가 나와 영상 13.9초의 4배가 됐다.
  82자로 줄여서 맞췄다. **자막이 정보를 나르고 VO 는 뼈대만** 말하는 게
  빠른 컷 영상에서는 오히려 낫다 — 처음부터 이 예산으로 대본을 써라.

### render_short.py 렌더 방식
- 상단 바(y 0~300, 불투명): 원본 배너·워터마크 가림 + **공정위 문구 상시 노출**
- 하단 바(y 1060~화면끝): 원본 자막 가림 + **VO 싱크 새 자막**
- VO atempo 배속 + 영상 끝프레임 홀드(tpad)로 길이 정렬
- 바 위치·폰트 크기 등은 JSON에서 덮어쓰기 가능(`top_bar_h`, `bottom_bar_y`, `caption_size` …)
- 검증: 새 렌더러로 다시 뽑은 `mirra_final.mp4` 가 기존 파일과 **바이트 단위 동일**(1,578,679 bytes / 16.60s)

## 6-2. 블로그 파이프라인

```
[상품 후보·모델명·사양]   ← 나 (tools/danawa_specs.py) 또는 사용자 캡처
        ↓
[쿠팡·토스 실제 가격·후기·링크]  ← 사용자 (내 환경에서 두 사이트 모두 403)
        ↓  캡처를 채팅에 올리면 내가 읽어서 JSON 으로 정리
posts_data/<id>.json
        ↓
python3 tools/make_blogpost.py posts_data/<id>.json   # 블로거용 HTML
python3 tools/make_preview.py  posts_data/<id>.json   # 발행 전 미리보기
        ↓
blog/posts/<id>.html 을 블로거 "HTML 보기"에 붙여넣기 → 발행
```

**필수 페이지(소개·개인정보처리방침·연락처)는 발행 완료.**
블로거는 페이지에 커스텀 퍼머링크가 없어 **영문 제목으로 먼저 게시해 URL 을 고정한 뒤
제목만 한글로 바꾸는** 우회를 썼다 (자세히는 `blog/README.md`).

### 첫 글 현황 — 자동급식기
- 상품 **쿠팡 2 + 토스 2**. 본문 약 4,900자. 구조·디자인 확정(PLAN 1-6, 1-6-1).
- 파우시는 상품평 캡처를 받아 **실제 후기 기반 장단점**이 들어가 있다.
- 쿠팡 파트너스 **상품 배너(iframe)** 로 제품 이미지 해결 — 가격이 자동 갱신된다.
- **남은 것**: 페블펫 상품평 캡처 1개 / 제휴 링크 3개(페블펫·디토펫·신일전자) / 배너 3개(선택)

## 7. 지금 바로 할 일 (TODO)

**블로그 트랙 — 첫 글 발행까지**
1. **[사용자] 페블펫 IPF-W100 상품평 캡처** → 실제 후기 기반 장단점으로 교체
2. **[사용자] 제휴 링크 3개** — 페블펫(쿠팡 딥링크) / 디토펫·신일전자(**토스 "쉐어링크 공유하기"**)
   ⚠️ 토스는 일반 "공유하기"로 만든 링크는 **수익 0원**이다
3. **[선택] 쿠팡 파트너스 상품 배너 3개** — 이미지까지 넣으려면
4. **[나] 반영 후 발행** — 링크 받으면 바로
5. **[다음] 블로거 테마** — 본문은 정리됐지만 헤더·사이드바는 아직 기본 테마

**숏폼 트랙**
6. **[사용자] GitHub Pages 켜기**: Settings→Pages→Deploy from a branch→ `...-v92w7y` /root
7. **[사용자→나] 쿠파스 딥링크** → `make_landing.py --deeplink "<링크>"` 로 반영
8. **[확인] 가격/할인** 89,000→26,000 이 실제와 맞는지 (나는 쿠팡 접근 불가)
9. **[사용자] 업로드**: `assets/mirra_final.mp4` + `posts/mosquito.md` 캡션

## 8. 연결된 MCP (이 프로젝트에서 씀)
- **higgsfield**: generate_image/video/audio(TTS), models_explore, list_voices, media_import_url(공개 URL만), job_display. (업로드는 egress로 막힘)
- **github**: repo/actions. Pages 자동 enable은 토큰 권한으로 실패 → 수동 "deploy from branch" 사용.
- Canva: 영상 자동조립 시도했으나 실패(자기 맘대로 재생성, 한글 깨짐). 비추.

## 9. 새 상품으로 다음 영상 만드는 법 (요약)
1. `cp products/_template.json products/<id>.json` → 이름·가격·카피·자막 채우기
2. 사용자가 footage(`footage/`)와 VO(`vo_<id>.mp3`)를 repo에 업로드 → 내가 `git pull`
3. `prep_source.py` → `render_short.py --probe` 로 타이밍 확인 → `captions` 손보고 다시 `render_short.py`
4. `make_landing.py`, `make_post.py` 실행 후 push
5. 딥링크 받으면 `make_landing.py --deeplink "<링크>"` 로 갱신

## 10. 새 글 쓰는 법 (블로그, 요약)
1. 상품 후보를 정한다. **대분류가 아니라 「디토펫 반려동물 자동급식기」처럼 상품을 특정**해서
   사용자에게 검색 목록으로 준다 (사용자 요청, 2026-07-29).
2. 사용자가 쿠팡·토스 화면을 캡처 → 내가 읽어 `posts_data/<id>.json` 작성
   - 검색 목록에 없는 사양(정전 대비·습식·세척·소음)은 **추측하지 말고 비워 둔다**
   - 상품평 캡처를 받으면 `pros`/`cons`/`review_insight` 에 실제 근거를 넣는다
3. 제휴 링크를 `link` 에, 파트너스 배너를 `banner` 에 넣는다 (없으면 버튼이 자동 비활성)
4. `make_blogpost.py` → `make_preview.py` → 확인 → 블로거에 붙여넣기
