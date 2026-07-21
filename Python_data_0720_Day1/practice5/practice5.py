import time

import pandas as pd
import polars as pl
import duckdb

CSV = 'data/events_large.csv'

# STEP 1 · 기준선 — Pandas (Eager, 단일 스레드)
start = time.perf_counter()
res_pandas = (pd.read_csv(CSV)
              .query('amount > 0')
              .groupby('event_type')
              .agg(cnt=('amount', 'count'), avg=('amount', 'mean'))
              .sort_values('cnt', ascending=False)
              .reset_index())
t_pandas = (time.perf_counter() - start) * 1000
print(f'Pandas: {t_pandas:.0f} ms')
print(res_pandas)

# STEP 2 · Polars Lazy — scan_csv(계획) + collect(실행)
start = time.perf_counter()
res_polars = (pl.scan_csv(CSV)
              .filter(pl.col('amount') > 0)
              .group_by('event_type')
              .agg(pl.len().alias('cnt'), pl.col('amount').mean().alias('avg'))
              .sort('cnt', descending=True)
              .collect())
t_polars = (time.perf_counter() - start) * 1000
print(f'\nPolars: {t_polars:.0f} ms')
print(res_polars)

# STEP 3 · DuckDB — CSV 파일을 SQL로 직접 조회
start = time.perf_counter()
res_duck = duckdb.sql(f"""
    SELECT event_type, COUNT(amount) AS cnt, AVG(amount) AS avg
    FROM '{CSV}'
    WHERE amount > 0
    GROUP BY event_type
    ORDER BY cnt DESC
""").df()
t_duck = (time.perf_counter() - start) * 1000
print(f'\nDuckDB: {t_duck:.0f} ms')
print(res_duck)

# STEP 4 · ★ 결과 일치 검증 — 정렬·타입·컬럼순서를 맞춘 뒤 비교
a = res_pandas.sort_values('event_type').reset_index(drop=True)
b = res_polars.to_pandas().sort_values('event_type').reset_index(drop=True)
c = res_duck.sort_values('event_type').reset_index(drop=True)
pd.testing.assert_frame_equal(a, b, check_dtype=False, atol=1e-6)
pd.testing.assert_frame_equal(a, c, check_dtype=False, atol=1e-6)
print('\n 세 엔진 결과 일치!')

# STEP 5 · 벤치마크 표 (Pandas 기준 배속)
print('\n' + '=' * 32)
print(f"{'엔진':<10}{'시간(ms)':>10}{'배속':>10}")
base = t_pandas
for name, t in sorted([('Pandas', t_pandas), ('Polars', t_polars), ('DuckDB', t_duck)], key=lambda x: x[1]):
    print(f'{name:<10}{t:>10.0f}{base / t:>9.1f}x')
