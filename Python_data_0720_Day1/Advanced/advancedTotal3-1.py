"""advancedTotal3-1 - Total3 + 한 걸음 더 (Plotly 임베드 · 알림 · 실패 재시도).

python advancedTotal3-1.py                # 1회 실행 (차트 임베드 리포트 + 알림)
python advancedTotal3-1.py --interval 60  # 60초마다 반복 (Ctrl+C로 중지)
"""

import argparse
import json
import os
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.error import URLError

import pandas as pd
import plotly.express as px
from jinja2 import Template

# 프로젝트 루트 기준 경로 (이 파일은 Advanced/ 안에 있음)
BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    data_path: Path = BASE_DIR / "data" / "sales_raw.csv"
    output_dir: Path = BASE_DIR / "output"
    title: str = "일일 매출 리포트"
    top_n: int = 10
    max_retries: int = 3
    # 알림에 넣을 공개 리포트 링크 (누구나 클릭해서 열 수 있는 웹 주소)
    report_url: str = (
        "https://claude.ai/code/artifact/db4569e3-2f59-4909-a5e8-21e66e4a840d"
    )
    sender_name: str = "SKALA 매출 리포트"  # 알림 발신자 이름


CONFIG = Config()


# ③ 실패 재시도 — 실습 3의 지수 백오프 재사용 (데이터가 아직 없을 수 있음)
def load_with_retry(path: Path, max_retries: int = 3) -> pd.DataFrame:
    for attempt in range(max_retries):
        try:
            return pd.read_csv(path)
        except FileNotFoundError:
            if attempt == max_retries - 1:
                raise
            wait = 2**attempt  # 1 → 2 → 4초
            print(f"데이터 없음, {wait}초 후 재시도")
            time.sleep(wait)


# 집계 — 순수 함수 (데이터 → 값, 파일 안 건드림)
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


# ① Plotly 임베드 — fig.to_html(full_html=False)로 조각 HTML 생성
def build_chart(by_category: list[dict]) -> str:
    cdf = pd.DataFrame(by_category)
    fig = px.bar(cdf, x="category", y="amount", title="카테고리별 매출")
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


# render()가 쓰는 리포트 HTML 틀 (주석 아닌 실제 문자열, 지우면 실행 에러)
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
<h2>인터랙티브 차트</h2>
{{ chart | safe }}
</body></html>
"""


def render(data: dict, chart_html: str, cfg: Config) -> Path:
    html = Template(TEMPLATE).render(
        title=cfg.title,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        chart=chart_html,
        **data,
    )
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = cfg.output_dir / f"report_adv_{stamp}.html"
    out.write_text(html, encoding="utf-8")
    return out


# ② 알림 — 리포트 생성 후 Slack/Discord 웹훅으로 링크 발송
#    환경변수 REPORT_WEBHOOK_URL이 있으면 실제 발송, 없으면 dry-run(로그만).
#    자격증명(웹훅 URL)은 하드코딩하지 않고 환경변수로만 주입한다.
#      export REPORT_WEBHOOK_URL="https://hooks.slack.com/services/..."
def notify(path: Path) -> None:
    # 공개 웹 링크를 발송 (환경변수 REPORT_URL로 덮어쓸 수 있음)
    url = os.environ.get("REPORT_URL", CONFIG.report_url)
    # <url>로 감싸면 Discord가 링크 미리보기 카드를 만들지 않는다 (링크는 클릭 가능)
    msg = f"📊 일일 매출 리포트 생성 완료 → <{url}>"
    webhook = os.environ.get("REPORT_WEBHOOK_URL")

    if not webhook:  # URL 없으면 발송하지 않고 로그만 (로컬 파일도 함께 표시)
        print(f"[알림·dry-run] {msg}  (로컬 파일: {path.name})")
        return

    # username으로 발신자 이름 지정, Slack("text")·Discord("content") 둘 다 전송
    payload = {"content": msg, "text": msg, "username": CONFIG.sender_name}
    body = json.dumps(payload).encode("utf-8")
    # User-Agent 없으면 Discord(Cloudflare)가 403으로 막는다 → 반드시 지정
    headers = {"Content-Type": "application/json", "User-Agent": "SKALA-report/1.0"}
    req = urllib.request.Request(webhook, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[알림·발송] status={resp.status} → {msg}")
    except URLError as error:  # 발송 실패해도 리포트 생성은 죽지 않게
        print(f"[알림·실패] {error} — {msg}")


# 세 방식(루프·schedule·cron)이 모두 이 함수 하나만 부름
def run_once() -> Path:
    df = load_with_retry(CONFIG.data_path, CONFIG.max_retries)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["amount"] = df["quantity"] * df["unit_price"] * (1 - df["discount"])

    data = aggregate(df, CONFIG.top_n)
    chart = build_chart(data["by_category"])
    path = render(data, chart, CONFIG)
    print(f"리포트 생성: {path}")
    notify(path)
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

    try:
        while True:  # 경량 루프 (의존성 0)
            run_once()
            time.sleep(args.interval)
    except KeyboardInterrupt:  # Ctrl+C → 깔끔하게 종료
        print("\n중지됨 (Ctrl+C)")


if __name__ == "__main__":
    main()
