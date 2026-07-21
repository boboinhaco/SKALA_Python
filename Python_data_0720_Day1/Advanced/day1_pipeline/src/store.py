"""store.py — 검증 데이터 저장 및 CSV vs Parquet 성능 비교

[프로그램 설명]
    [Day 1] 종합 실습 "데이터 수집 미니 파이프라인"의 3단계.
    schema.validate_all()을 통과한 데이터를 pandas DataFrame으로 만들어
    CSV와 Parquet 두 형식으로 저장하고, 각 형식의 쓰기/읽기 시간과
    파일 크기를 측정해 비교표로 출력한다.

[측정 방법]
    - time.perf_counter()로 각 저장/읽기를 여러 번(REPEAT) 반복해
      중앙값(median)을 취한다. 데이터가 작을수록 1회 측정은 노이즈가 크기 때문.
    - 파일 크기는 os.stat().st_size(bytes)로 비교.

[변경 내역]
    2026-07-22  최초 작성 — DataFrame 변환 + CSV/Parquet 저장·성능 비교
"""

from __future__ import annotations

import asyncio
import statistics
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from src.collect import collect_all
from src.schema import ValidatedData, validate_all

# 이 파일(src/) 기준 프로젝트 루트 → data/ 폴더에 저장
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

# 반복 측정 횟수 (데이터가 작아 1회 측정은 편차가 큼 → 중앙값 사용)
REPEAT = 30


def to_frames(data: ValidatedData) -> dict[str, pd.DataFrame]:
    """검증 통과 데이터를 이름별 DataFrame으로 변환.

    - weather: 시간별 레코드 리스트 → 여러 행
    - country/geo: 단일 레코드 → 1행
    """
    return {
        "weather": pd.DataFrame([h.model_dump() for h in data.weather]),
        "country": pd.DataFrame([data.country.model_dump()]),
        "geo": pd.DataFrame([data.geo.model_dump()]),
    }


def _median_seconds(action: Callable[[], None], repeat: int = REPEAT) -> float:
    """action을 repeat번 실행한 소요 시간(초)의 중앙값을 반환."""
    samples: list[float] = []
    for _ in range(repeat):
        start = time.perf_counter()
        action()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def benchmark_one(name: str, df: pd.DataFrame) -> dict:
    """단일 DataFrame을 CSV·Parquet로 저장/읽기하며 시간·크기 측정.

    반환: {rows, csv_write, csv_read, csv_size, pq_write, pq_read, pq_size}
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATA_DIR / f"{name}.csv"
    pq_path = DATA_DIR / f"{name}.parquet"

    # 쓰기 시간 (index=False로 불필요한 인덱스 컬럼 저장 방지)
    csv_write = _median_seconds(lambda: df.to_csv(csv_path, index=False))
    pq_write = _median_seconds(lambda: df.to_parquet(pq_path, index=False))

    # 읽기 시간
    csv_read = _median_seconds(lambda: pd.read_csv(csv_path))
    pq_read = _median_seconds(lambda: pd.read_parquet(pq_path))

    return {
        "rows": len(df),
        "csv_write": csv_write,
        "csv_read": csv_read,
        "csv_size": csv_path.stat().st_size,
        "pq_write": pq_write,
        "pq_read": pq_read,
        "pq_size": pq_path.stat().st_size,
    }


def _fmt_ms(seconds: float) -> str:
    """초 → 밀리초 문자열."""
    return f"{seconds * 1000:.3f} ms"


def print_report(results: dict[str, dict]) -> None:
    """측정 결과를 형식별 비교표로 출력."""
    print(f"\n{'=' * 68}")
    print(f"CSV vs Parquet 성능 비교 (각 항목 {REPEAT}회 중앙값)")
    print("=" * 68)
    header = f"{'dataset':<10}{'rows':>6}{'write(CSV/PQ)':>24}{'read(CSV/PQ)':>24}"
    print(header)
    print("-" * 68)
    for name, r in results.items():
        writes = f"{_fmt_ms(r['csv_write'])} / {_fmt_ms(r['pq_write'])}"
        reads = f"{_fmt_ms(r['csv_read'])} / {_fmt_ms(r['pq_read'])}"
        print(f"{name:<10}{r['rows']:>6}{writes:>24}{reads:>24}")
    print("-" * 68)
    # 파일 크기 비교
    print("파일 크기(byte)  CSV / Parquet:")
    for name, r in results.items():
        print(f"  {name:<10} {r['csv_size']:>8} / {r['pq_size']:>8}")
    print("=" * 68)

    # 간단한 해석 (weather 기준 — 유일하게 행 수가 의미 있는 데이터)
    w = results.get("weather")
    if w:
        faster_read = "Parquet" if w["pq_read"] < w["csv_read"] else "CSV"
        smaller = "Parquet" if w["pq_size"] < w["csv_size"] else "CSV"
        print(
            f"[해석] weather({w['rows']}행) — 읽기 더 빠름: {faster_read}, "
            f"파일 더 작음: {smaller}"
        )
        print(
            "  ※ Parquet은 컬럼형·압축 포맷이라 데이터가 커질수록 읽기 속도·"
            "용량에서 유리해진다."
        )


def store_and_report(data: ValidatedData) -> dict[str, dict]:
    """검증 통과 데이터를 저장·성능측정하고 리포트를 출력한 뒤 결과 반환.

    수집·검증을 이미 마친 호출자(main.py 등)가 재수집 없이 재사용하는 공용 함수.
    """
    frames = to_frames(data)
    results = {name: benchmark_one(name, df) for name, df in frames.items()}
    print_report(results)
    return results


def run() -> dict[str, dict]:
    """수집 → 검증 → 저장·성능 측정 → 리포트 (단독 실행 진입점)."""
    raw = asyncio.run(collect_all())
    data = validate_all(raw)
    return store_and_report(data)


if __name__ == "__main__":
    run()
