"""main.py — 데이터 수집 미니 파이프라인 전체 실행 진입점

[프로그램 설명]
    [Day 1] 종합 실습의 5단계를 한 번에 실행하고 결과를 화면에 출력한다.
      1) 비동기 수집(asyncio.gather)   → src/collect.py
      2) 스키마 검증(Pydantic v2)      → src/schema.py
      3) 저장·성능 비교(CSV/Parquet)   → src/store.py
    각 단계의 결과(수집 요약·검증 통과 샘플·성능 비교표)를 순서대로 보여준다.

[변경 내역]
    2026-07-22  최초 작성 — 전체 단계 실행 및 결과 출력

[실행]
    python main.py               # day1_pipeline/ 에서 (venv 활성화 후)
"""

from __future__ import annotations

import asyncio

from src.collect import collect_all, print_collection_summary
from src.schema import validate_all
from src.store import store_and_report


def main() -> None:
    # ── 1) 비동기 수집 ────────────────────────────────────────────────
    print("=" * 68)
    print("[1/3] 비동기 수집 (asyncio.gather — 3개 API 동시)")
    print("=" * 68)
    raw = asyncio.run(collect_all())
    print_collection_summary(raw)  # collect.py와 동일한 요약 로직 재사용

    # ── 2) 스키마 검증 ────────────────────────────────────────────────
    print("\n" + "=" * 68)
    print("[2/3] 스키마 검증 (Pydantic v2 — 타입·범위)")
    print("=" * 68)
    data = validate_all(raw)
    print(f"  weather : {len(data.weather)}건 검증 통과")
    print(f"            예) {data.weather[0].model_dump()}")
    print(f"  country : {data.country.name} ({data.country.alpha3Code})")
    print(f"  geo     : {data.geo.city}, {data.geo.country} (IP {data.geo.query})")

    # ── 3) 저장 및 성능 비교 ─────────────────────────────────────────
    print("\n" + "=" * 68)
    print("[3/3] CSV·Parquet 저장 및 읽기/쓰기 성능 비교")
    print("=" * 68)
    store_and_report(data)  # store.py와 동일한 저장·측정 로직 재사용 (재수집 없음)

    print("\n✅ 파이프라인 완료 — 저장 파일: data/*.csv, data/*.parquet")


if __name__ == "__main__":
    main()
