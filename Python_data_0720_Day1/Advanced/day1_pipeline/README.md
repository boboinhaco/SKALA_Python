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

## 실습 준비 (완료)
```bash
# 1) venv 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate        # (Windows: .venv\Scripts\activate)

# 2) 패키지 설치
pip install -r requirements.txt

# 3) API 엔드포인트 설정 (실제 URL은 .env에만)
cp .env.example .env             # 이후 .env에 실제 URL 입력
```

## 진행 단계 (채점 기준)
- [x] **환경 준비** — venv + requirements.txt 설치
- [ ] **비동기 수집** — asyncio + httpx, `asyncio.gather()`로 3개 API 동시 수집 (35점)
- [ ] **스키마 검증** — 필드 추출 → Pydantic v2 모델로 타입·범위 검증
- [ ] **저장·성능 비교** — CSV·Parquet 저장 후 읽기/쓰기 시간 측정 (45점)
- [ ] **테스트·커밋** — pytest 검증 테스트 + `ruff check` (10점)
- [ ] **완성도** — 주석/머리말 정리 (10점)

## 폴더 구조
```
day1_pipeline/
├── .env              # 실제 API URL (git 제외)
├── .env.example      # URL 템플릿 (git 포함)
├── .gitignore
├── requirements.txt
├── README.md
├── src/              # 파이프라인 코드
├── tests/            # pytest 스키마 검증
└── data/             # 저장 결과 (csv·parquet, git 제외)
```
