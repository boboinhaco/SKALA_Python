"""Advanced 4-1 - 정제 규칙을 함수로 분리 + pytest 테스트.

    python advanced4-1.py   # 실제 데이터 파이프라인 실행
    pytest advanced4-1.py   # 정제 규칙 단위 테스트
"""

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_FILE = BASE_DIR / "data" / "sales_raw.csv"


def clean_price(df: pd.DataFrame) -> pd.DataFrame:
    """타입 정규화 — 숫자/날짜/category (실패값은 NaN)."""
    df = df.copy()
    for col in ("unit_price", "quantity", "discount"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["category"] = df["category"].astype("category")
    return df


def fill_missing(df: pd.DataFrame) -> pd.DataFrame:
    """결측 처리 — unit_price는 카테고리별 중앙값, region은 'Unknown'."""
    df = df.copy()
    df["unit_price"] = df.groupby("category", observed=True)["unit_price"].transform(
        lambda s: s.fillna(s.median())
    )
    df["region"] = df["region"].fillna("Unknown").astype("category")
    return df


def remove_outliers(df: pd.DataFrame, cols=("unit_price", "quantity"), k: float = 1.5) -> pd.DataFrame:
    """이상치 처리 — IQR 윈저라이징(경계선까지 clip)."""
    df = df.copy()
    for col in cols:
        s = df[col]
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        df[col] = s.clip(lower=q1 - k * iqr, upper=q3 + k * iqr)
    return df


def run_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """타입 → 결측 → 이상치 → amount 계산."""
    df = clean_price(df)
    df = fill_missing(df)
    df = remove_outliers(df)
    df["amount"] = (df["quantity"] * df["unit_price"] * (1 - df["discount"])).round(1)
    return df


def main() -> None:
    raw = pd.read_csv(DATA_FILE)
    print("정제 전 결측:\n", raw.isna().sum(), sep="")

    clean = run_pipeline(raw)

    print("\n정제 후 결측:\n", clean.isna().sum(), sep="")
    print("\n정제 후 dtypes:\n", clean.dtypes, sep="")
    print("\n카테고리별 요약:")
    print(
        clean.groupby("category", observed=True).agg(
            건수=("unit_price", "count"),
            평균단가=("unit_price", "mean"),
            총매출=("amount", "sum"),
        ).round(1)
    )


# pytest 테스트 — 문자열 가격/결측/이상치를 일부러 심은 소형 데이터로 검증
def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_id": ["A", "B", "C", "D", "E"],
            "order_date": ["2025-01-01", "2025-01-02", "bad-date", "2025-01-04", "2025-01-05"],
            "region": ["Seoul", None, "Busan", "Seoul", None],
            "category": ["Home", "Home", "Home", "Food", "Food"],
            "quantity": [1, 2, 3, 4, 1000],
            "unit_price": ["100", "200", None, "300", "400"],
            "discount": [0, 0.1, 0, 0, 0],
        }
    )


def test_clean_price_converts_types():
    out = clean_price(_sample_df())
    assert pd.api.types.is_numeric_dtype(out["unit_price"])
    assert out["unit_price"].iloc[0] == 100
    assert out["order_date"].isna().sum() == 1  # 'bad-date' → NaT
    assert isinstance(out["category"].dtype, pd.CategoricalDtype)


def test_fill_missing_leaves_no_na():
    out = fill_missing(clean_price(_sample_df()))
    assert out["unit_price"].isna().sum() == 0
    assert out["region"].isna().sum() == 0
    assert out.loc[2, "unit_price"] == 150  # Home(100,200,NaN) 중앙값
    assert (out["region"] == "Unknown").sum() == 2


def test_remove_outliers_clips_extremes():
    cleaned = fill_missing(clean_price(_sample_df()))
    out = remove_outliers(cleaned)
    assert out["quantity"].max() < cleaned["quantity"].max()  # 1000 눌림
    assert len(out) == len(cleaned)


def test_run_pipeline_end_to_end():
    out = run_pipeline(_sample_df())
    assert "amount" in out.columns
    assert out["amount"].isna().sum() == 0


def test_functions_do_not_mutate_input():
    original = _sample_df()
    snapshot = original.copy()
    remove_outliers(fill_missing(clean_price(original)))
    pd.testing.assert_frame_equal(original, snapshot)


if __name__ == "__main__":
    main()
