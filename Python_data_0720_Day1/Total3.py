"""종합실습 3 - 분석 자동화 · 리포트 생성 (관심사의 분리).

설정(Config) · 로직(aggregate/render) · 실행(run_once/main)을 분리한다.
루프·schedule·cron 어느 방식으로 돌려도 결국 run_once() 하나만 부른다 → 일관성.

    python Total3.py                # 1회 실행 → output/에 타임스탬프 HTML 생성
    python Total3.py --interval 60  # 60초마다 반복 (Ctrl+C로 중지)
"""

import argparse
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Template


# ── 설정: frozen dataclass (만든 뒤엔 못 바꿈 → 몰래 바뀌는 버그 차단) ──
@dataclass(frozen=True)
class Config:
    data_path: Path = Path("data/sales_raw.csv")
    output_dir: Path = Path("output")
    title: str = "일일 매출 리포트"
    top_n: int = 10


CONFIG = Config()


# ── 로직 ①: 집계 — 순수 함수 (데이터 → 값, 파일 안 건드림) ──
def aggregate(df: pd.DataFrame, top_n: int = 10) -> dict:
    return {
        "kpi": {
            "총매출": int(df["amount"].sum()),
            "주문수": len(df),
            "평균주문액": round(df["amount"].mean(), 1),
        },
        "by_category": (
            df.groupby("category", observed=True)["amount"]
            .sum()
            .sort_values(ascending=False)
            .head(top_n)
            .round(0)
            .reset_index()
            .to_dict("records")
        ),
    }


# ── 로직 ②: Jinja2 렌더링 — 디자인(HTML)과 데이터(Python) 분리 ──
TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body { font-family: sans-serif; margin: 40px; }
  table { border-collapse: collapse; }
  th, td { border: 1px solid #ccc; padding: 8px 14px; }
  th { background: #1F3864; color: white; }
</style></head><body>
<h1>{{ title }}</h1>
<p>생성 시각: {{ generated_at }}</p>
<h2>핵심 지표</h2>
<ul>
{% for k, v in kpi.items() %}
  <li>{{ k }}: {{ '{:,}'.format(v) }}</li>
{% endfor %}
</ul>
<h2>카테고리별 매출</h2>
<table>
  <tr><th>카테고리</th><th>매출</th></tr>
{% for row in by_category %}
  <tr><td>{{ row.category }}</td><td>{{ '{:,}'.format(row.amount) }}</td></tr>
{% endfor %}
</table>
</body></html>
"""


def render(data: dict, cfg: Config) -> Path:
    html = Template(TEMPLATE).render(
        title=cfg.title,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **data,
    )
    cfg.output_dir.mkdir(parents=True, exist_ok=True)  # 없으면 생성
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 타임스탬프 → 이력 보존
    out = cfg.output_dir / f"report_{stamp}.html"
    out.write_text(html, encoding="utf-8")
    return out


# ── 실행: 세 방식(루프·schedule·cron)이 모두 이 함수 하나만 부른다 ──
def run_once() -> Path:
    df = pd.read_csv(CONFIG.data_path)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["amount"] = df["quantity"] * df["unit_price"] * (1 - df["discount"])

    data = aggregate(df, CONFIG.top_n)
    path = render(data, CONFIG)
    print(f"리포트 생성: {path}")
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--interval", type=int, default=0, help="초 단위 반복. 0이면 1회만 실행"
    )
    args = ap.parse_args()

    if args.interval == 0:
        run_once()
        return

    while True:  # 경량 루프 (의존성 0), Ctrl+C로 중지
        run_once()
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
