"""종합실습 1 - 비동기 ETL 파이프라인 (Extract → Transform → Load → run 조율).

실습 3(비동기 수집)과 실습 2(Pydantic 검증)를 하나의 재사용 파이프라인으로 엮고,
pytest로 각 단계를 검증한다. 네트워크·파일은 가장자리로, 계산은 순수 함수로.

    python Total1.py        # 파이프라인 실행 → 요약 딕셔너리 출력
    pytest Total1.py -v     # 단위 테스트 6개
"""

import asyncio
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field, ValidationError, field_validator


# ── 모델 (실습 2 재사용) ────────────────────────────────────
class Product(BaseModel):
    id: int
    name: str
    category: str
    price: float = Field(gt=0)  # 음수 가격 거부

    @field_validator("category")
    @classmethod
    def lower_category(cls, value: str) -> str:
        return value.strip().lower()  # 앞뒤 공백 제거 + 소문자화


# ── Extract: 비동기 수집 · 동시성 제한 · 재시도 (실습 3) ──────
async def fetch(item_id: int) -> dict:
    """모의 요청 — 10의 배수는 음수 가격(오염 데이터)으로 반환."""
    await asyncio.sleep(0.01)  # 네트워크 대기 흉내 (time.sleep 아님!)
    price = -1.0 if item_id % 10 == 0 else round(10 + item_id, 2)
    return {
        "id": item_id,
        "name": f"product_{item_id}",
        "category": " FOOD ",
        "price": price,
    }


async def extract(
    ids: list[int], max_concurrent: int = 10, max_retries: int = 3
) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrent)  # 백프레셔

    async def one(i: int):
        async with sem:
            for attempt in range(max_retries):  # 지수 백오프 재시도
                try:
                    return await fetch(i)
                except Exception:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(2**attempt)

    results = await asyncio.gather(*[one(i) for i in ids], return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]  # 실패는 격리


# ── Transform: Pydantic 검증 → 유효/무효 분리 (실습 2) ───────
def transform(raw: list[dict]) -> tuple[list[Product], list[dict]]:
    """입력만 받아 결과만 돌려주는 순수 함수 (네트워크·파일 안 건드림)."""
    valid, invalid = [], []
    for row in raw:
        try:
            valid.append(Product(**row))
        except ValidationError as error:
            invalid.append({"data": row, "errors": error.errors()})
    return valid, invalid


# ── Load: DataFrame → CSV · Parquet 저장 ────────────────────
def load(valid: list[Product], out_dir: str = "output") -> pd.DataFrame:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([v.model_dump() for v in valid])
    df.to_csv(f"{out_dir}/products.csv", index=False)
    df.to_parquet(f"{out_dir}/products.parquet", index=False)  # 타입 보존
    return df


# ── Orchestrate: run()은 조율만, 일은 E·T·L이 한다 ──────────
async def run(ids: list[int], out_dir: str = "output") -> dict:
    raw = await extract(ids)  # E
    valid, invalid = transform(raw)  # T
    df = load(valid, out_dir)  # L
    return {
        "total": len(raw),
        "valid": len(valid),
        "invalid": len(invalid),
        "rows_saved": len(df),
    }


# ── pytest 테스트 6개 (함수 하나 = 테스트 하나) ─────────────
def test_category_lowercased():  # 스키마 정규화
    valid, _ = transform([{"id": 1, "name": "A", "category": " FOOD ", "price": 10}])
    assert valid[0].category == "food"


def test_negative_price_rejected():  # 가격 규칙(음수 거부)
    valid, invalid = transform(
        [{"id": 1, "name": "A", "category": "food", "price": -5}]
    )
    assert len(valid) == 0
    assert len(invalid) == 1


def test_missing_field_rejected():  # 필수 필드 누락 거부
    valid, invalid = transform([{"id": 1, "name": "A", "price": 10}])  # category 누락
    assert len(valid) == 0
    assert len(invalid) == 1


def test_valid_invalid_counts_match():  # 유효/무효 분리 건수 일치 (하나도 안 샘)
    rows = [
        {"id": 1, "name": "A", "category": "food", "price": 10},
        {"id": 2, "name": "B", "category": "home", "price": 20},
        {"id": 3, "name": "C", "category": "home", "price": -1},
    ]
    valid, invalid = transform(rows)
    assert len(valid) + len(invalid) == len(rows)


def test_parquet_roundtrip(tmp_path):  # 저장 후 다시 읽어도 같은가
    df = pd.DataFrame({"id": [1, 2], "price": [10.5, 20.0]})
    p = tmp_path / "test.parquet"
    df.to_parquet(p, index=False)
    pd.testing.assert_frame_equal(df, pd.read_parquet(p))


def test_run_pipeline_end_to_end(tmp_path):  # 전체 파이프라인 (임시 폴더에 저장)
    summary = asyncio.run(run(list(range(20)), out_dir=str(tmp_path)))
    assert summary == {"total": 20, "valid": 18, "invalid": 2, "rows_saved": 18}
    assert (tmp_path / "products.csv").exists()
    assert (tmp_path / "products.parquet").exists()


if __name__ == "__main__":
    print(asyncio.run(run(list(range(60)))))
