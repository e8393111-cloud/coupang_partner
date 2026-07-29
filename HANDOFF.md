# 🚀 쿠팡 파트너스 수익화 프로젝트 — 핸드오프 (이어서 작업용)

> 마지막 업데이트: 2026-07-28 · 다른 세션에서 이 파일 읽고 그대로 이어가면 됨.

## 0. 한 줄 요약
쿠팡 파트너스 **숏폼(릴스/쇼츠/틱톡) 반자동 수익화** 프로젝트. 첫 상품(**UV 모기퇴치기**)으로 완성 영상 + 상세페이지까지 제작 완료. 파이프라인 검증됨.

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
- VO 톤: **Hana 보이스 + 홈쇼핑 쇼호스트 톤** 채택. qwen speech_rate가 잘 안 먹음 → **속도는 mux 때 ffmpeg atempo로** 조정.
- TTS에서 **"끝" 글자 깨짐**(끕) → 우회 표현 사용.
- 공정위 문구 **필수**: 영상 내(상단) + 캡션 맨앞 + 인포크링크/상세페이지 상단. (캡션만은 위험 — "더보기"로 잘림)

## 3. 환경 제약 (반드시 인지)
- **egress 차단**: 쿠팡/구글/쇼핑몰/cloudfront **다운로드 불가**(403), higgsfield 스토리지 **업로드 불가**. WebFetch도 쿠팡 403.
- **우회 = 공개 GitHub repo가 "파일 다리"**:
  - 내가 만든 것 → repo push → 사용자는 `raw.githubusercontent.com/.../<branch>/...` 로 봄
  - 사용자가 준 파일(footage, vo.mp3) → repo 업로드 → 내가 `git pull`로 가져와 편집
  - higgsfield 생성물(영상/이미지/오디오)은 내가 못 받음 → 톤 확인용으로 URL만 주고, 합성은 repo에 올라온 파일로만.
- repo는 **공개(public)** 상태 (Pages·raw URL 위해). 개발 브랜치: **`claude/coupang-partners-monetization-v92w7y`**
- ffmpeg: 시스템에 없음 → `pip install imageio-ffmpeg` (7.0.2 static, libx264 O, **drawtext 없음** → 자막은 **PIL로 PNG 그려 overlay**). 한글 폰트 = `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc` (한글 됨, 이모지 X). `pip install Pillow` 필요.

## 4. repo 구조
```
index.html                         # 수익화 대시보드(별개 툴, PWA)
manifest.json
HANDOFF.md                         # ← 이 파일
VIDEO_PROJECT_모기퇴치기.md         # 영상 소스 클립 6개 링크 + 캡션 가이드(초기 AI버전)
assets/
  mosquito-lamp-bedside.jpg        # 실제 제품 사진(사용자 업로드)
  mosquito-lamp-detail.jpg         # 쿠팡 상세 스크린샷(UI 있음)
  mirra_cleaned.mp4                # Mirra 초벌 → 후처리(배너/워터마크 제거, 15s)
  mirra_final.mp4                  # ★최종 영상(홈쇼핑 VO+자막싱크+공정위, 16.6s)
  test_render.mp4                  # ffmpeg 배관 테스트
vo.mp3                             # 최종 VO(홈쇼핑 톤, 사용자가 업로드한 것)
tools/
  plumbing_test.py                 # ffmpeg+한글자막 배관 테스트
  mirra_postproc.py                # Mirra 영상 트림+배너/워터마크 크롭
  mux_vo.py                        # 영상에 VO(1.5x) 합성(초기)
  resub.py                         # ★원본자막 가리고 VO싱크 새자막+공정위+VO 합성(최종 렌더러)
p/mosquito.html                    # ★모기퇴치기 상세페이지(랜딩) — Pages용
```

## 5. 완성물 URL
- **최종 영상**: `https://raw.githubusercontent.com/e8393111-cloud/coupang_partner/claude/coupang-partners-monetization-v92w7y/assets/mirra_final.mp4`
- **상세페이지**(Pages 켜지면): `https://e8393111-cloud.github.io/coupang_partner/p/mosquito.html`
- 대시보드 아티팩트: `https://claude.ai/code/artifact/d6464cf6-1dfb-4b75-b94a-7081359c59e3`

## 6. 작동하는 파이프라인 (반자동)
```
[상품 리서치·훅·스크립트]  ← 나 (에이전트 병렬)
        ↓
[Mirra로 초벌 광고 뽑기]  ← 사용자 (또는 raw 클립 소싱)
        ↓  repo에 업로드
[ffmpeg 후처리: 트림·배너/워터마크 제거]  ← tools/mirra_postproc.py
[VO 생성: 한국어 홈쇼핑 TTS]  ← higgsfield generate_audio (아래 세팅)
        ↓  사용자가 vo.mp3 repo 업로드
[원본자막 가리고 VO싱크 자막+공정위+VO(1.5x) 합성]  ← tools/resub.py
        ↓
[완성 mp4 push]  →  사용자 다운로드 → 틱톡/릴스 업로드
```

### VO(TTS) 재사용 세팅 (higgsfield generate_audio)
- model: `qwen_audio_tts`, language: `ko`
- voice: **Hana** — voice_type `preset`, voice_id `c25f78a0-714e-42af-8da3-a399cef94968`
- instruction(홈쇼핑): "홈쇼핑 쇼호스트처럼 열정적이고 친근하게 설득하듯, 뚝뚝 끊지 말고 부드럽게 이어서, 자연스럽게 흐르듯이, 활기차게"
- speech_rate 1.15~1.3 (효과 적음), pitch_rate 1.03. **실제 속도는 mux 때 atempo=1.5로.**
- ⚠️ "끝" 등 일부 글자 깨짐 → 대본에서 회피.

### resub.py 렌더 방식
- 상단 바(y 0~300, 불투명): 원본 배너·워터마크 가림 + **공정위 문구 상시 노출**
- 하단 바(y 1060~화면끝): 원본 자막 가림 + **VO 싱크 새 자막**
- 자막 타이밍: `silencedetect`로 VO 문장 경계 잡아 매핑
- VO 1.5배(atempo) + 영상 끝프레임 홀드로 길이 정렬

## 7. 지금 바로 할 일 (TODO)
1. **[사용자] GitHub Pages 켜기**: Settings→Pages→Source "Deploy from a branch"→ `claude/coupang-partners-monetization-v92w7y` /root → Save. 그럼 상세페이지 URL 활성.
2. **[사용자] 쿠파스 딥링크 생성** → `p/mosquito.html`의 `COUPANG_DEEPLINK` 2군데를 실제 딥링크로 교체(내가 해줄 수 있음).
3. **[확인] 가격/할인**: 상세페이지 89,000→26,000 표시가 실제 쿠팡과 맞는지. 다르면 숫자 조정.
4. **[사용자] 링크 세팅**: 인포크링크(or 상세페이지 URL)를 인스타/틱톡 바이오에. **틱톡은 비즈니스 계정 전환**해야 바이오 링크 생김.
5. **[사용자] 업로드**: mirra_final.mp4 + 캡션(맨앞 공정위 문구+해시태그). 틱톡은 앱에서 트렌딩 사운드 얹기.
6. **[다음] 반응 데이터 보고** 훅/상품 조정 → 잘 되면 **전체 흐름 Skill로 고정**.

## 8. 연결된 MCP (이 프로젝트에서 씀)
- **higgsfield**: generate_image/video/audio(TTS), models_explore, list_voices, media_import_url(공개 URL만), job_display. (업로드는 egress로 막힘)
- **github**: repo/actions. Pages 자동 enable은 토큰 권한으로 실패 → 수동 "deploy from branch" 사용.
- Canva: 영상 자동조립 시도했으나 실패(자기 맘대로 재생성, 한글 깨짐). 비추.

## 9. 새 상품으로 다음 영상 만드는 법 (요약)
1. 상품 정하고(여름 소싱 리스트는 VIDEO_PROJECT에 참고), Mirra로 초벌 뽑거나 raw 클립 소싱
2. repo `footage/`(raw) 또는 `assets/`에 업로드
3. `tools/mirra_postproc.py`(Mirra면) 또는 새 트림 스크립트로 정리
4. VO는 위 세팅으로 higgsfield 생성 → 사용자 vo.mp3 업로드
5. `tools/resub.py`의 대본/구간/가격만 바꿔 렌더 → push
6. 상세페이지는 `p/mosquito.html` 복제해서 상품만 교체
