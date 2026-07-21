"""collect.py — 비동기 데이터 수집 (asyncio + httpx)

[프로그램 설명]
    [Day 1] 종합 실습 "데이터 수집 미니 파이프라인"의 1단계.
    Open-Meteo · Countries.dev · ip-api 3개 공개 API를 asyncio.gather()로
    "동시에" 호출해 원본 JSON을 수집한다. 순차 호출 대비 총 대기 시간을 줄인다.

[보안 유의]
    API 엔드포인트(URL)는 코드에 하드코딩하지 않는다.
    Open-Meteo(open api)·ip-api URL은 .env에만 두고 os.environ으로 주입받으며,
    .env는 .gitignore로 제외되어 깃/인터넷에 올라가지 않는다.

[변경 내역]
    2026-07-21  최초 작성 — 3개 API 비동기 수집 (asyncio.gather)

[실행]
    python -m src.collect        # day1_pipeline/ 에서 실행
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

# .env 로드 → 실제 API URL을 환경변수로 주입 (코드에 URL 하드코딩 금지)
load_dotenv()

# 수집 대상: (이름, 환경변수 키). 실제 URL은 .env에서 읽는다.
_API_ENV_KEYS: dict[str, str] = {
    "weather": "OPENMETEO_URL",  # Open-Meteo: 서울 3일 기온·강수확률
    "country": "COUNTRIES_URL",  # Countries.dev: 한국 국가 정보
    "geo": "IPAPI_URL",  # ip-api: IP 기반 지역 정보
}

# 네트워크 타임아웃(초) — 응답이 없을 때 무한정 대기하지 않도록 상한을 둔다.
REQUEST_TIMEOUT = 10.0


@dataclass(frozen=True)
class FetchResult:
    """개별 API 수집 결과 (이름 + 원본 JSON)."""

    name: str
    payload: dict


def _load_endpoints() -> dict[str, str]:
    """.env에서 3개 API URL을 읽어 {이름: URL} 로 반환.

    누락되었거나(빈 값) http(s)로 시작하지 않는(자리표시자 등) URL이 있으면
    어떤 키가 문제인지 명시해 즉시 실패시킨다. 잘못된 URL을 그대로 요청해
    httpx가 알기 어려운 예외(UnsupportedProtocol)를 던지는 상황을 방지한다.
    """
    endpoints: dict[str, str] = {}
    invalid: list[str] = []
    for name, env_key in _API_ENV_KEYS.items():
        url = os.environ.get(env_key, "")
        # 빈 값이거나 http:// · https:// 로 시작하지 않으면 잘못된 값으로 간주
        if not url.startswith(("http://", "https://")):
            invalid.append(env_key)
        else:
            endpoints[name] = url
    if invalid:
        raise RuntimeError(
            f".env의 다음 URL이 비었거나 형식이 잘못됐습니다: {', '.join(invalid)}\n"
            "  → .env.example의 자리표시자(<...입력>)를 실제 URL로 바꿔주세요.\n"
            "  → 특히 cp .env.example .env 로 기존 .env를 덮어쓰지 않았는지 확인!"
        )
    return endpoints


async def _fetch_one(client: httpx.AsyncClient, name: str, url: str) -> FetchResult:
    """단일 API를 비동기로 호출해 JSON을 반환.

    HTTP 오류(4xx/5xx)는 raise_for_status()로 예외화하여 gather 상위에서 처리.
    """
    resp = await client.get(url)
    resp.raise_for_status()
    return FetchResult(name=name, payload=resp.json())


async def collect_all() -> dict[str, dict]:
    """3개 API를 asyncio.gather()로 동시에 수집해 {이름: JSON} 반환.

    - 하나의 AsyncClient를 공유해 연결을 재사용한다.
    - gather로 세 요청을 병렬 발행 → 총 소요 = 가장 느린 응답 1건 수준.
    """
    endpoints = _load_endpoints()
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        tasks = [_fetch_one(client, name, url) for name, url in endpoints.items()]
        results: list[FetchResult] = await asyncio.gather(*tasks)
    return {r.name: r.payload for r in results}


def main() -> None:
    """수집 결과를 요약 출력 (동시 수집 동작 확인용)."""
    raw = asyncio.run(collect_all())
    print("수집 완료 — 응답 키 요약:")
    for name, payload in raw.items():
        keys = (
            list(payload)[:5] if isinstance(payload, dict) else type(payload).__name__
        )
        print(f"  [{name}] 최상위 키: {keys}")


if __name__ == "__main__":
    main()
