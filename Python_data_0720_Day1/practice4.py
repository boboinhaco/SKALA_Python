"""실습 4 - Pandas 데이터 정제 파이프라인 (진단 → 타입 → 결측 → 이상치 → 집계)."""

import pandas as pd

# STEP 0 · 진단 — 어디가 얼마나 더러운지 파악
df = pd.read_csv('data/sales_raw.csv')

print('=' * 60, 'STEP 0 · 진단', sep='\n')
print('shape:', df.shape)
df.info()
print(df.describe())
print('\n[결측 개수]')
print(df.isna().sum())
print('\n[상위 5행]')
print(df.head())

# STEP 1 · 타입 정규화 — errors='coerce'는 변환 실패값을 NaN으로
print('\n' + '=' * 60, 'STEP 1 · 타입 정규화', sep='\n')
df['unit_price'] = pd.to_numeric(df['unit_price'], errors='coerce')
df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
df['discount'] = pd.to_numeric(df['discount'], errors='coerce')
df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
df['category'] = df['category'].astype('category')
print(df.dtypes)

# 타입 변환 후 결측이 늘 수 있으므로 결측 처리는 반드시 이 다음에 한다
print('\n[타입 변환 후 결측 개수]')
print(df.isna().sum())

# STEP 2 · 결측 처리 — 0/평균이 아니라 그룹별 중앙값으로
print('\n' + '=' * 60, 'STEP 2 · 결측 처리 (전/후)', sep='\n')
print('처리 전 unit_price 결측:', df['unit_price'].isna().sum())
print('처리 전 region     결측:', df['region'].isna().sum())

# transform은 행 수를 유지하므로 fillna에 바로 쓸 수 있다
df['unit_price'] = df.groupby('category', observed=True)['unit_price'] \
    .transform(lambda s: s.fillna(s.median()))
df['region'] = df['region'].fillna('Unknown').astype('category')

print('처리 후 unit_price 결측:', df['unit_price'].isna().sum())
print('처리 후 region     결측:', df['region'].isna().sum())

# STEP 3 · 이상치 처리 — IQR 윈저라이징(삭제가 아니라 경계선까지 clip)
print('\n' + '=' * 60, 'STEP 3 · 이상치 처리 (전/후)', sep='\n')


def winsorize(s, k=1.5):
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    return s.clip(lower=q1 - k * iqr, upper=q3 + k * iqr)


print('처리 전 unit_price min/max:', df['unit_price'].min(), '/', df['unit_price'].max())
print('처리 전 quantity   min/max:', df['quantity'].min(), '/', df['quantity'].max())
df['unit_price'] = winsorize(df['unit_price'])
df['quantity'] = winsorize(df['quantity'])
print('처리 후 unit_price min/max:', df['unit_price'].min(), '/', df['unit_price'].max())
print('처리 후 quantity   min/max:', df['quantity'].min(), '/', df['quantity'].max())

# amount = 수량 × 단가 × (1 - 할인율)
df['amount'] = (df['quantity'] * df['unit_price'] * (1 - df['discount'])).round(1)

# STEP 4 · groupby.agg — 그룹별 세로 요약
print('\n' + '=' * 60, 'STEP 4 · groupby.agg (카테고리별)', sep='\n')
summary = df.groupby('category', observed=True).agg(
    건수=('unit_price', 'count'),
    평균단가=('unit_price', 'mean'),
    중앙단가=('unit_price', 'median'),
    총매출=('amount', 'sum'),
).round(1)
print(summary)

# STEP 5 · pivot_table — 가로세로 교차표
print('\n' + '=' * 60, 'STEP 5 · pivot_table (카테고리 × 지역)', sep='\n')
pivot = df.pivot_table(
    index='category', columns='region', values='amount',
    aggfunc='sum', fill_value=0, observed=True,
).round(0)
print(pivot)

# STEP 6 · merge — how 선택 주의, 전후 len() 비교 필수
print('\n' + '=' * 60, 'STEP 6 · merge (카테고리 담당팀)', sep='\n')
category_info = pd.DataFrame({
    'category': ['Electronics', 'Fashion', 'Home', 'Beauty', 'Food'],
    'team': ['가전팀', '패션팀', '리빙팀', '뷰티팀', '푸드팀'],
})
category_info['category'] = category_info['category'].astype('category')
before = len(df)
df = df.merge(category_info, on='category', how='left')
print(before, '→', len(df), '(행 수 유지 확인)')
print(df[['category', 'team']].head())

# STEP 7 · 체인 인덱싱 대신 .loc으로 지정
print('\n' + '=' * 60, 'STEP 7 · .loc으로 파생 컬럼', sep='\n')
df['high_value'] = 0
df.loc[df['amount'] > 500_000, 'high_value'] = 1
print('고액 주문(amount > 500,000) 건수:', int(df['high_value'].sum()))

# 최종 확인 — 성공 판정 기준
print('\n' + '=' * 60, '최종 dtypes', sep='\n')
print(df.dtypes)
print('\n최종 결측 개수(전 컬럼 0이어야 함):')
print(df.isna().sum())
