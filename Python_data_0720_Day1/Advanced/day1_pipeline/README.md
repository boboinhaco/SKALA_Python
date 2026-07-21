# [Day 1] 종합 실습 — 데이터 수집 미니 파이프라인

실무형 **수집 · 검증 · 품질** 파이프라인. asyncio+httpx로 3개 공개 API를 동시에 수집하고,
Pydantic v2로 스키마를 검증한 뒤 CSV·Parquet로 저장하며 읽기/쓰기 성능을 비교한다.

## 사용 API
| API | 용도 | 비고 |
|-----|------|------|
| Open-Meteo | 서울 3일 시간대별 기온·강수확률 | **URL은 `.env`에만** (깃 커밋 금지) |
| Countries.dev | 한국 국가 정보 | — |
| ip-api | IP 기반 지역 정보 | **URL은 `.env`에만** (깃 커밋 금지) |

> ⚠️ Open-Meteo(open api)와 ip-api의 실제 URL은 `.env`에 두고 절대 깃/인터넷에 올리지 않는다.
> 코드는 `os.environ`(python-dotenv)으로 URL을 주입받아 하드코딩을 피한다.

## 실행 방법

### 1. 최초 1회 — 환경 준비
```bash
# (1) venv 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate        # (Windows: .venv\Scripts\activate)

# (2) 패키지 설치
pip install -r requirements.txt

# (3) API 엔드포인트 설정 — .env가 아직 없을 때만 실행!
cp .env.example .env             # 이후 .env를 열어 실제 URL 입력
#   OPENMETEO_URL / IPAPI_URL 의 <...입력> 자리에 실제 URL을 채운다.
```
> ⚠️ `.env`가 이미 있으면 `cp .env.example .env`를 **다시 실행하지 말 것** — 실제 URL이
> 자리표시자로 덮어써져 실행 시 `UnsupportedProtocol` 오류가 난다.

### 2. 전체 파이프라인 실행 (결과 보기)
```bash
python main.py
```
수집 → 검증 → 저장·성능비교 결과가 순서대로 출력된다. 저장물은 `data/*.csv`, `data/*.parquet`.

### 3. 단계별 실행 / 검사
```bash
python -m src.collect     # 1단계) 비동기 수집만 (응답 키 요약)
python -m src.store       # 3단계) 저장·성능비교 (내부에서 수집·검증까지 수행)
pytest                    # 스키마 검증 테스트 11건 (네트워크 불필요)
ruff check .              # 코드 스타일 검사
ruff format --check .     # 포매팅 준수 확인
```

## 실행 예시 출력
```
[1/3] 비동기 수집 (asyncio.gather — 3개 API 동시)
  [weather] 응답 최상위 키(일부): ['latitude', 'longitude', ...]
  ...
[2/3] 스키마 검증 (Pydantic v2 — 타입·범위)
  weather : 72건 검증 통과
  country : Korea (Republic of) (KOR)
  geo     : Ashburn, United States (IP 8.8.8.8)
[3/3] CSV·Parquet 저장 및 읽기/쓰기 성능 비교
  dataset   rows   write(CSV/PQ)      read(CSV/PQ)
  weather     72   0.21 / 0.37 ms     0.24 / 0.51 ms
  [해석] weather(72행) — 읽기 더 빠름: CSV, 파일 더 작음: CSV
```

## 진행 단계 (채점 기준)
- [x] **환경 준비** — venv + requirements.txt 설치
- [x] **비동기 수집** — asyncio + httpx, `asyncio.gather()`로 3개 API 동시 수집 (35점)
- [x] **스키마 검증** — 필드 추출 → Pydantic v2 모델로 타입·범위 검증
- [x] **저장·성능 비교** — CSV·Parquet 저장 후 읽기/쓰기 시간 측정 (45점)
- [x] **테스트·커밋** — pytest 11건 통과 + `ruff check` 오류 0 (10점)
- [x] **완성도** — 주석/머리말 정리 (10점)

## 폴더 구조
```
day1_pipeline/
├── .env              # 실제 API URL (git 제외)
├── .env.example      # URL 템플릿 (git 포함)
├── .gitignore
├── requirements.txt  # 의존 패키지
├── pyproject.toml    # pytest · ruff 설정
├── README.md
├── main.py           # ★ 전체 파이프라인 실행 진입점
├── src/
│   ├── collect.py    # 1) 비동기 수집 (asyncio.gather)
│   ├── schema.py     # 2) Pydantic v2 스키마 검증
│   └── store.py      # 3) CSV/Parquet 저장·성능 비교
├── tests/
│   └── test_schema.py  # pytest 스키마 검증 테스트 11건
└── data/             # 저장 결과 (csv·parquet, git 제외)
```
