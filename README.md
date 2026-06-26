# kupas — 쿠팡 파트너스 숏폼 수익화 파이프라인

스레드(Threads)·틱톡에서 흔히 보이는 **쿠팡 파트너스(쿠파스) 수익화 패턴**을
한 흐름으로 자동화합니다.

> 신박한 상품 발굴 → 후킹 카피 생성 → 파트너스 딥링크 → 게시·성과 추적

`todaypick100` 류의 게시물처럼, "이게 된다고?" 싶은 상품에 스크롤을 멈추게 하는
첫 줄을 붙이고, 단축 제휴 링크와 광고 고지를 자동으로 조립합니다.

## 동작 방식

```
[발굴]            [카피]                 [링크]               [추적]
쿠팡 Open API  →  Claude(opus-4-8)  →   파트너스 딥링크   →   SQLite
상품검색/베스트     플랫폼별 후킹 카피     subId 로 채널 분리     클릭·주문·수수료
```

- **발굴** — 키워드 검색 또는 카테고리 베스트로 임팩트 있는 상품을 찾습니다.
- **카피** — 스레드/틱톡 각각의 톤에 맞춰 후킹 첫 줄·본문·해시태그를 생성합니다.
- **링크** — 상품 URL을 단축 제휴 링크로 변환하고, `subId`로 플랫폼·상품별
  클릭/전환을 분리 추적합니다.
- **추적** — 생성 콘텐츠와 게시 성과(클릭·주문·수수료)를 SQLite에 기록합니다.

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
# 키워드로 상품 발굴 → 스레드/틱톡 카피 생성
python -m kupas run --keyword "캠핑 텐트" --limit 3

# 카테고리 베스트로 발굴, 틱톡만
python -m kupas run --category 1016 --platforms tiktok --limit 5

# 저장된 콘텐츠 목록
python -m kupas list

# 게시물 성과 기록 (post id 는 list/DB 에서 확인)
python -m kupas perf 1 --clicks 120 --orders 4 --revenue 22680

# 성과 요약
python -m kupas stats
```

## 코드로 쓰기

```python
from kupas.pipeline import Pipeline

pipe = Pipeline()
pieces = pipe.run(keyword="무선 청소기", limit=3)
for piece in pieces:
    for cap in piece.captions:
        print(cap.platform, "→", cap.render(piece.deeplink, ""))
```

## 구조

```
kupas/
  config.py     환경설정 로딩
  coupang.py    쿠팡 파트너스 Open API (HMAC, 검색/베스트/딥링크)
  captions.py   Claude 기반 플랫폼별 후킹 카피
  models.py     Product / Caption / ContentPiece
  storage.py    SQLite 콘텐츠·성과 추적
  pipeline.py   발굴→카피→링크→저장 오케스트레이션
  cli.py        커맨드라인
tests/
  test_pipeline.py   mock 모드 스모크 테스트
```

## 주의 (운영 시)

- **광고 고지 의무** — 모든 게시물에 "쿠팡 파트너스 활동의 일환으로 수수료를
  제공받습니다" 고지가 자동 포함됩니다. 빼지 마세요.
- **과장·허위 표현 금지** — 카피 생성 시스템 프롬프트가 사실 기반 흥미 유발만
  하도록 제약하지만, 게시 전 검수를 권장합니다.
- **자동 게시는 포함하지 않음** — 각 플랫폼의 API 정책/약관 때문에 게시는 수동
  또는 별도 연동이 필요합니다. 본 도구는 게시 직전까지(카피+링크)를 책임집니다.
