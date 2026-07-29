# 🚀 쿠팡 파트너스 수익화 프로젝트 — 핸드오프 (이어서 작업용)

> 마지막 업데이트: 2026-07-29 · 다른 세션에서 이 파일 읽고 그대로 이어가면 됨.

## 0. 한 줄 요약
쿠팡 파트너스 **숏폼(릴스/쇼츠/틱톡) 반자동 수익화** 프로젝트. 첫 상품(**UV 모기퇴치기**)으로 완성 영상 + 상세페이지까지 제작 완료. 파이프라인 검증됨.
2026-07-29: 1회성 스크립트를 **설정(JSON) 기반 파이프라인**으로 정리 → 새 상품은 `products/<id>.json` 하나만 채우면 됨.

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
- **egress 차단**: 쿠팡/구글/쇼핑몰/cloudfront **다운로드 불가**(403), higgsfield 스토리지 **업로드 불가**. WebFetch도 쿠팡 403.
- **우회 = 공개 GitHub repo가 "파일 다리"**:
  - 내가 만든 것 → repo push → 사용자는 `raw.githubusercontent.com/.../<branch>/...` 로 봄
  - 사용자가 준 파일(footage, vo.mp3) → repo 업로드 → 내가 `git pull`로 가져와 편집
  - higgsfield 생성물(영상/이미지/오디오)은 내가 못 받음 → 톤 확인용으로 URL만 주고, 합성은 repo에 올라온 파일로만.
- repo는 **공개(public)** 상태 (Pages·raw URL 위해)
- 세션 시작할 때마다 설치 필요: `pip install imageio-ffmpeg Pillow`
  - ffmpeg 7.0.2 static (libx264 O, **drawtext 없음** → 자막은 PIL로 PNG 그려 overlay)
  - 한글 폰트 = `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`

## 4. repo 구조
```
index.html                     # 수익화 대시보드(별개 툴, PWA)
manifest.json
HANDOFF.md                     # ← 이 파일
VIDEO_PROJECT_모기퇴치기.md     # 초기 AI 클립 6개 링크 + 캡컷 조립안(참고용 기록)
products/
  _template.json               # ★새 상품 시작점 (복사해서 값만 채움)
  mosquito.json                # ★모기퇴치기 전체 설정(소스·자막·상세페이지·캡션)
tools/
  prep_source.py               # ① 소스 크롭/트림/이어붙이기
  render_short.py              # ② VO 합성 + 공정위 상단바 + 자막 번인 (최종 렌더러)
  make_landing.py              # ③ 상세페이지 생성
  landing_template.html        #    └ 상세페이지 템플릿(디자인은 여기서 수정)
  make_post.py                 # ④ 플랫폼별 업로드 캡션 키트 생성
  plumbing_test.py             # ffmpeg+한글자막 배관 테스트
assets/
  mirra_cleaned.mp4            # 정리된 소스(15.03s)
  mirra_final.mp4              # ★최종 영상(홈쇼핑 VO+자막싱크+공정위, 16.60s)
  mosquito-lamp-bedside.jpg    # 실제 제품 사진(사용자 업로드)
  mosquito-lamp-detail.jpg     # 쿠팡 상세 스크린샷(UI 있음)
  test_render.mp4              # ffmpeg 배관 테스트 결과
vo.mp3                         # 최종 VO(홈쇼핑 톤, 사용자가 업로드한 것)
p/mosquito.html                # 상세페이지(자동 생성물 — 직접 고치지 말 것)
posts/mosquito.md              # 업로드 캡션 키트(자동 생성물)
```
> `p/*.html`, `posts/*.md`, `assets/*final*.mp4` 는 **생성물**이다. 고칠 땐 `products/<id>.json` 또는 `tools/landing_template.html` 을 고치고 다시 생성할 것.
> (2026-07-29에 1회성 스크립트 `resub.py`·`mux_vo.py`·`mirra_postproc.py` 는 위 도구들로 대체되어 삭제. 필요하면 git 히스토리에 있음.)

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

### render_short.py 렌더 방식
- 상단 바(y 0~300, 불투명): 원본 배너·워터마크 가림 + **공정위 문구 상시 노출**
- 하단 바(y 1060~화면끝): 원본 자막 가림 + **VO 싱크 새 자막**
- VO atempo 배속 + 영상 끝프레임 홀드(tpad)로 길이 정렬
- 바 위치·폰트 크기 등은 JSON에서 덮어쓰기 가능(`top_bar_h`, `bottom_bar_y`, `caption_size` …)
- 검증: 새 렌더러로 다시 뽑은 `mirra_final.mp4` 가 기존 파일과 **바이트 단위 동일**(1,578,679 bytes / 16.60s)

## 7. 지금 바로 할 일 (TODO)
1. **[사용자] GitHub Pages 켜기**: Settings→Pages→Source "Deploy from a branch"→ **`claude/coupang-partners-monetization-v92w7y`** (또는 `...-3xx5n7`, 둘 다 같음) /root → Save.
2. **[사용자→나] 쿠파스 딥링크**: 링크만 주면 `python3 tools/make_landing.py products/mosquito.json --deeplink "<링크>"` 로 한 방에 반영. 지금은 딥링크가 안 박혀서 **구매 버튼이 비활성** 상태(잘못된 링크로 유입되지 않게 일부러 막아둠).
3. **[확인] 가격/할인**: 상세페이지 89,000→26,000 표시가 실제 쿠팡과 맞는지. 다르면 `products/mosquito.json` 의 `landing.price` / `list_price` / `sticky_cta` 만 고치고 재생성. (나는 쿠팡 접근이 막혀 확인 불가)
4. **[사용자] 링크 세팅**: 인포크링크(or 상세페이지 URL)를 인스타/틱톡 바이오에. **틱톡은 비즈니스 계정 전환**해야 바이오 링크 생김.
5. **[사용자] 업로드**: `assets/mirra_final.mp4` + `posts/mosquito.md` 의 캡션 복붙. 틱톡은 앱에서 트렌딩 사운드 얹기.
6. **[다음] 반응 데이터 보고** 훅/상품 조정 → 잘 되면 전체 흐름 Skill로 고정.
7. **[다음] 2번째 상품**: `products/_template.json` 복사해서 시작. footage/VO만 사용자가 주면 나머지는 자동.

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
