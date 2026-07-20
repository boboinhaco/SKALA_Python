"""종합실습 2 - EDA + 통계 검정 + ML 파이프라인 (이탈 예측).

순서를 지키는 것이 절반: EDA → 시각화 → 통계 검정 → ML.
Pipeline으로 전처리를 train 안에서만 학습시켜 데이터 누수를 구조적으로 막는다.

    python Total2.py   # 전 과정 실행 → 통계량·ROC-AUC 출력, output/에 리포트·모델 저장
"""

from pathlib import Path

import joblib
import pandas as pd
import plotly.express as px
import polars as pl
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

DATA_FILE = "data/telco_churn.csv"
OUT_DIR = Path("output")
OUT_DIR.mkdir(parents=True, exist_ok=True)
RANDOM_STATE = 42  # 재현성 고정


# STEP 0 · EDA — 데이터에 뭐가 있는지부터, 타깃 비율 먼저
df = pl.read_csv(DATA_FILE, null_values=[""])
print("shape:", df.shape)
print("columns:", df.columns)
print(df.describe())

churn_ratio = df.group_by("churn").len().sort("churn")
print("\n[타깃 비율] 0=잔류 / 1=이탈")
print(churn_ratio)
# 불균형이면 accuracy는 못 쓴다 → 그래서 ROC-AUC를 지표로 사용

# STEP 1 · 이탈 vs 잔류 그룹 비교 (가설 세우기)
print("\n[이탈 여부별 평균]")
print(
    df.group_by("churn")
    .agg(
        pl.col("monthly_charges").mean().alias("평균요금"),
        pl.col("tenure_months").mean().alias("평균가입기간"),
        pl.len().alias("인원"),
    )
    .sort("churn")
)

# 이후 단계는 pandas로 (Plotly·scipy·sklearn이 pandas를 받는다)
pdf = df.to_pandas()

# STEP 2 · Plotly 시각화 → HTML 리포트
fig = px.box(pdf, x="churn", y="monthly_charges", title="이탈 여부별 월 요금 분포")
html_path = OUT_DIR / "churn_charges.html"
fig.write_html(html_path)

# STEP 3 · 통계 검정 — 눈으로 본 것을 숫자로 확인
# ① t-검정: 숫자(요금)를 두 그룹 간 비교
charge_churn = pdf.loc[pdf["churn"] == 1, "monthly_charges"]
charge_stay = pdf.loc[pdf["churn"] == 0, "monthly_charges"]
t_stat, t_p = stats.ttest_ind(charge_churn, charge_stay, equal_var=False)
print(f"\nt-검정 p = {t_p:.2e}  (요금 차이)")

# ② 카이제곱: 범주(계약유형) vs 범주(이탈)
table = pd.crosstab(pdf["contract"], pdf["churn"])
chi2, chi_p, dof, expected = stats.chi2_contingency(table)
print(f"카이제곱 p = {chi_p:.2e}  (계약유형 vs 이탈)")
# 해석: 요금·계약유형이 이탈과 '유의한 연관'. 단, 연관 ≠ 인과.

# STEP 4~6 · 전처리(누수 방지) + 모델 학습
num_cols = [
    "tenure_months",
    "monthly_charges",
    "total_charges",
    "num_services",
    "senior",
]
cat_cols = ["contract", "payment_method", "gender"]

preprocessor = ColumnTransformer(
    [
        (
            "num",
            Pipeline(
                [
                    ("imp", SimpleImputer(strategy="median")),  # 결측 → 중앙값
                    ("sc", StandardScaler()),  # 스케일 통일
                ]
            ),
            num_cols,
        ),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),  # 순서 관계 방지
    ]
)

X = pdf[num_cols + cat_cols]
y = pdf["churn"].astype(int)
X_tr, X_te, y_tr, y_te = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=RANDOM_STATE,
    stratify=y,  # 이탈 비율 유지
)

pipe = Pipeline(
    [
        ("prep", preprocessor),
        ("model", RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE)),
    ]
)
pipe.fit(X_tr, y_tr)  # 전처리+모델이 train 안에서만 학습 (누수 없음)

# STEP 7 · 평가 — 불균형이므로 정확도가 아니라 ROC-AUC
proba = pipe.predict_proba(X_te)[:, 1]  # 확률을 쓴다 (0/1 아님)
auc = roc_auc_score(y_te, proba)
print(f"\nROC-AUC = {auc:.3f}")
print(classification_report(y_te, pipe.predict(X_te)))

model_path = OUT_DIR / "churn_model.joblib"
joblib.dump(pipe, model_path)  # 전처리까지 통째로 저장
print("저장:", html_path, "/", model_path)
