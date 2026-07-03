# kupas — 쿠팡 파트너스 숏폼 수익화 파이프라인

스레드(Threads)·틱톡에서 흔히 보이는 **쿠팡 파트너스(쿠파스) 수익화 패턴**을
한 흐름으로 자동화합니다.

> 신박한 상품 발굴 → 후킹 카피 생성 → 파트너스 딥링크 → 게시·성과 추적

`todaypick100` 류의 게시물처럼, "이게 된다고?" 싶은 상품에 스크롤을 멈추게 하는
첫 줄을 붙이고, 단축 제휴 링크와 광고 고지를 자동으로 조립합니다.

## 국내 + 글로벌 동시진행 (멀티마켓)

한 번의 실행으로 **국내(쿠팡/한국어)와 글로벌(Amazon·AliExpress/영어)**을 동시에
돌립니다. 마켓에 따라 소스·언어·통화·광고고지가 자동으로 바뀝니다.

| `--market` | 소스 | 언어 | 통화 |
|-----------|------|------|------|
| `kr` | 쿠팡 파트너스 | 한국어 | KRW |
| `global` | Amazon Associates | English | USD |
| `ali` | AliExpress | English | USD |
| `all` | 국내 + 글로벌 동시 | 각각 | 각각 |

```bash
python -m kupas run --market all --keyword "massager" --top 3        # 국내+글로벌 동시
python -m kupas run --market global --audience 40+ --platforms reels shorts --media
```

- **`--audience 40+`**: 40대 이상 타깃 — 건강·홈·주방·정원·반려 등 카테고리에 가점,
  카피 톤도 혜택 중심·명확하게. (릴스·쇼츠 권장)
- **캡컷 TTS 대본**: `--media` 시 각 소재에 **캡컷 텍스트읽기에 그대로 붙일 나레이션
  대본**(`tts_script`)이 언어에 맞춰 생성됩니다 → 캡컷 자동자막으로 바로 자막화.
- 실제 Amazon/AliExpress API는 추후 연결(현재 mock). 쿠팡은 키 넣으면 실 API.

## 동작 방식 — 분야별 에이전트 사슬

각 분야가 독립 에이전트로 동작하고 오케스트레이터가 조율합니다(경량 방식 —
역할 모듈 + 필요한 곳에만 Claude 프롬프트).

```
Brief(키워드/카테고리·플랫폼·목표개수) 가 사슬을 따라 흐른다

 ① Discovery ─▶ ② Curation ─▶ ③ Copy ─▶ ④ Media(선택) ─▶ ⑤ Publish
    발굴           선별(★핵심)    카피       소재 기획         게시준비
  후보 상품       점수·랭킹·컷    후킹 카피  샷리스트·프롬프트  딥링크+고지+저장
        └──────────── Orchestrator 가 조율 / 단계별 로그 ────────────┘
```

| 에이전트 | 역할 | Claude |
|----------|------|--------|
| **DiscoveryAgent** | 키워드/카테고리로 후보 상품 발굴 (+키워드 확장) | 선택 |
| **CurationAgent** ★ | 수수료·가격대·로켓·신박함으로 터질 상품 선별 | 선택(비전) |
| **CopyAgent** | 스레드/틱톡 후킹 카피 (+ few-shot, 대체 후킹) | 필수 |
| **MediaAgent** | 틱톡·릴스 소재 기획 (샷리스트·자막·생성 프롬프트) | 선택 |
| **PublishAgent** | 딥링크·광고고지 조립, 성과 추적 저장 | 없음 |

### 선별 에이전트 (상품 자동 선별)

"카피보다 상품 보는 눈이 8할"이라, 발굴한 상품을 **2단계 깔때기**로 거릅니다.

1. **휴리스틱 점수** (전수, 무료) — API 데이터만으로:
   - 수수료 기대값 = `가격 × 카테고리 수수료율`
   - 가격대 적합도 = sweet-spot 곡선(5만원 부근 피크)
   - 로켓배송 보너스
2. **신박도 점수** (`--vision`, 상위 후보만) — 상품명+이미지를 Claude가 보고
   "이게 된다고?" 호기심 유발도를 0~100으로 평가. 비주얼 임팩트 큰 상품을 끌어올림.

상위 `--top`개만 다음 단계로 넘겨, 카피 생성 토큰도 그만큼만 씁니다.
수수료율 테이블·가중치는 `kupas/agents/curation.py`에서 조정합니다.

### 카피 에이전트 (후킹 강화)

실제로 터진 게시물의 첫 줄 구조를 **후킹 아키타입**(`kupas/exemplars.py`)으로
정리해 카피 생성에 **few-shot**으로 주입합니다 — "이거 만든 사람 상 줘야 하는 거
아니냐?", "이 가격에 이게 된다고?" 류의 검증된 패턴을 상품에 맞게 새로 씁니다.
플랫폼별 카피마다 **대체 후킹 2개**(A/B 테스트용)도 함께 뽑아, 어떤 첫 줄이 더
잘 먹히는지 비교할 수 있습니다. Claude 키가 없으면 아키타입을 돌려가며 다양한
mock 후킹을 생성합니다.

### 미디어 에이전트 (소재 기획)

`--media` 를 켜면 각 카피에 맞는 **소재 기획서**를 만듭니다 — 3초 후킹부터 시작하는
샷리스트(장면+자막), BGM/페이싱 가이드, 그리고 바로 붙여넣어 쓸 수 있는 **이미지·
영상 생성 프롬프트**까지. 실제 영상 생성(외부 유료 API)은 하지 않고 "무엇을 어떻게
찍을지/생성할지" 직전 단계를 책임집니다. 생성 도구 연동은 별도 옵션으로 확장 가능.

> **mock 모드** — API 키가 없어도 가짜 상품·카피·링크로 전체 흐름이 그대로
> 돌아갑니다. 키를 넣는 순간 실 API로 전환됩니다.

## 설치

```bash
pip install -r requirements.txt
cp .env.example .env   # 키 입력 (없으면 mock 모드로 동작)
```

`.env` 키:

| 변수 | 용도 |
|------|------|
| `COUPANG_ACCESS_KEY` / `COUPANG_SECRET_KEY` | 쿠팡 파트너스 Open API 인증키 |
| `ANTHROPIC_API_KEY` | 카피 생성용 Claude API 키 |
| `KUPAS_CAPTION_MODEL` | 카피 모델 (기본 `claude-opus-4-8`) |
| `KUPAS_SUBID_PREFIX` | 성과 추적용 subId 접두 (기본 `kupas`) |
| `KUPAS_DB_PATH` | SQLite 경로 (기본 `kupas.db`) |

쿠팡 인증키는 [쿠팡 파트너스](https://partners.coupang.com) → 내 정보 → 인증키
발급에서 받습니다(파트너스 가입·승인 필요).

## 사용법

```bash
# 에이전트 로스터·역할 확인
python -m kupas agents

# 발굴+선별 랭킹만 (카피 미생성, 무료 triage)
python -m kupas discover --keyword "캠핑 텐트" --top 5

# 전체 사슬: 발굴→선별→카피→게시준비
python -m kupas run --keyword "캠핑 텐트" --top 3

# 미디어 소재 기획서까지 (샷리스트·생성 프롬프트)
python -m kupas run --keyword "캠핑 텐트" --top 3 --media

# 카테고리 베스트로 발굴, 틱톡만, 신박도 점수까지
python -m kupas run --category 1016 --platforms tiktok --top 5 --vision

# 게시 큐 보기 / 예약 / 스케줄러용 export
python -m kupas queue
python -m kupas schedule 2 --at "2026-07-01 19:00"
python -m kupas export --out queue.csv          # Make/Buffer 로 연동
python -m kupas push                            # Make 웹훅으로 게시 큐 전송(반자동)

# 성과 수집: 파트너스 리포트 CSV import (subId 매칭, 플랫폼별 분리)
python -m kupas import-report report.csv

# 저장된 콘텐츠 목록 / 수동 성과 기록 / 성과 요약
python -m kupas list
python -m kupas perf 1 --clicks 120 --orders 4 --revenue 22680
python -m kupas stats
```

### 게시 에이전트 (반자동 게시 + 성과 수집)

Threads/TikTok **완전 자동 게시**는 공식 앱 심사 승인이 필요해, 본 도구는 **반자동**
흐름을 제공합니다.

- **게시 큐 / 예약** — 플랫폼별 게시본문·딥링크를 큐로 관리하고 `schedule` 로 예약.
- **export / push** — `export` 로 CSV·JSON 내보내 Buffer·Metricool 등에 연결하거나,
  `push` 로 Make 웹훅(`KUPAS_MAKE_WEBHOOK`)에 보내 시나리오로 자동 게시.
- **성과 자동 수집** — 쿠팡 Open API엔 실적 리포트 엔드포인트가 없어, 파트너스
  대시보드에서 받은 **리포트 CSV를 `import-report` 로 흡수**합니다. subId를
  **플랫폼별로** 부여하므로(`kupas-tiktok-…` / `kupas-threads-…`) 스레드·틱톡 어느
  쪽이 전환을 내는지 분리해서 집계됩니다.

## 코드로 쓰기

```python
from kupas.agents import Orchestrator, Brief

orch = Orchestrator()
result = orch.run(Brief(keyword="무선 청소기", target_count=3))
for piece in result.pieces:
    print(int(piece.score.total), piece.product.name)
    for cap in piece.captions:
        print(cap.platform, "→", cap.render(piece.deeplink, ""))

# 발굴+선별만 (무료 triage)
shortlist = orch.curate(Brief(keyword="캠핑", target_count=5)).shortlist
```

기존 `kupas.pipeline.Pipeline` 도 호환 래퍼로 유지됩니다.

## 구조

```
kupas/
  config.py     환경설정 로딩
  sources.py    멀티마켓 소스 추상화 (쿠팡/Amazon/AliExpress)      ← 도구
  coupang.py    쿠팡 파트너스 Open API (HMAC, 검색/베스트/딥링크)  ← 도구
  captions.py   Claude 기반 플랫폼별 후킹 카피                      ← 도구
  exemplars.py  검증된 후킹 아키타입·예시 게시물 (few-shot)          ← 도구
  report.py     파트너스 리포트 CSV 파서 (성과 수집)                 ← 도구
  storage.py    SQLite 콘텐츠·점수·게시큐·성과 추적                  ← 도구
  models.py     Product / ProductScore / ScoredProduct / Caption / ContentPiece
  agents/
    base.py         Brief · Agent 프로토콜 · AgentLog
    discovery.py    DiscoveryAgent  (발굴)
    curation.py     CurationAgent + 점수 엔진  (선별 ★)
    copy.py         CopyAgent  (카피)
    media.py        MediaAgent  (소재 기획)
    publish.py      PublishAgent  (게시준비)
    orchestrator.py Orchestrator  (사슬 조율)
  pipeline.py   호환 래퍼 (→ Orchestrator)
  cli.py        커맨드라인
tests/
  test_pipeline.py   에이전트 단위 + 오케스트레이터 통합 스모크 테스트
```

## 주의 (운영 시)

- **광고 고지 의무** — 모든 게시물에 "쿠팡 파트너스 활동의 일환으로 수수료를
  제공받습니다" 고지가 자동 포함됩니다. 빼지 마세요.
- **과장·허위 표현 금지** — 카피 생성 시스템 프롬프트가 사실 기반 흥미 유발만
  하도록 제약하지만, 게시 전 검수를 권장합니다.
- **자동 게시는 포함하지 않음** — 각 플랫폼의 API 정책/약관 때문에 게시는 수동
  또는 별도 연동이 필요합니다. 본 도구는 게시 직전까지(카피+링크)를 책임집니다.
