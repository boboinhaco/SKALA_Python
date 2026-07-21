"""test_schema.py — 스키마 검증(Pydantic v2) 단위 테스트

[프로그램 설명]
    schema.py의 검증 로직을 네트워크 없이 검증한다.
    - 정상 데이터는 통과하는지
    - 범위/타입을 벗어난 데이터는 ValidationError로 거부되는지
    - Open-Meteo 배열 평탄화와 길이 불일치 처리
    - validate_all()이 원본 JSON을 3종 모델로 묶어 검증하는지

[변경 내역]
    2026-07-22  최초 작성 — 정상/경계/오류 케이스 + validate_all 통합 테스트

[실행]
    pytest                       # advanced_day1_pipeline/ 에서
    pytest -v tests/test_schema.py
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schema import (
    CountryInfo,
    GeoInfo,
    WeatherHour,
    _extract_weather_hours,
    validate_all,
)


# ── 테스트용 원본 JSON 픽스처 (실제 API 응답 구조를 축약) ──────────────
@pytest.fixture
def raw_weather() -> dict:
    return {
        "hourly": {
            "time": ["2026-07-22T00:00", "2026-07-22T01:00"],
            "temperature_2m": [24.9, 25.1],
            "precipitation_probability": [100, 79],
        }
    }


@pytest.fixture
def raw_country() -> dict:
    return {
        "name": "Korea (Republic of)",
        "alpha3Code": "kor",  # 소문자 → 검증기에서 KOR로 정규화되어야 함
        "region": "Asia",
        "capital": "Seoul",
        "population": 51780579,
        "area": 100210,
    }


@pytest.fixture
def raw_geo() -> dict:
    return {
        "status": "success",
        "country": "United States",
        "countryCode": "US",
        "regionName": "Virginia",
        "city": "Ashburn",
        "lat": 39.03,
        "lon": -77.5,
        "timezone": "America/New_York",
        "query": "8.8.8.8",
    }


# ── WeatherHour: 정상 / 범위 밖 ────────────────────────────────────────
def test_weather_hour_ok():
    hour = WeatherHour(
        time="2026-07-22T00:00", temperature_2m=24.9, precipitation_probability=100
    )
    assert hour.temperature_2m == 24.9
    assert hour.precipitation_probability == 100


def test_weather_precip_over_100_rejected():
    # 강수확률 120% → 0~100 범위 밖 → 거부
    with pytest.raises(ValidationError):
        WeatherHour(
            time="2026-07-22T00:00", temperature_2m=25.0, precipitation_probability=120
        )


def test_weather_temperature_out_of_range_rejected():
    # 기온 999°C → -90~60 범위 밖 → 거부
    with pytest.raises(ValidationError):
        WeatherHour(
            time="2026-07-22T00:00", temperature_2m=999.0, precipitation_probability=10
        )


# ── CountryInfo: 정규화 / 잘못된 값 ────────────────────────────────────
def test_country_alpha3_uppercased(raw_country):
    country = CountryInfo.model_validate(raw_country)
    assert country.alpha3Code == "KOR"  # kor → KOR 정규화 확인


def test_country_population_must_be_positive(raw_country):
    raw_country["population"] = 0  # gt=0 위반
    with pytest.raises(ValidationError):
        CountryInfo.model_validate(raw_country)


# ── GeoInfo: status / 위경도 범위 ─────────────────────────────────────
def test_geo_status_fail_rejected(raw_geo):
    raw_geo["status"] = "fail"  # ip-api 실패 응답 → 거부
    with pytest.raises(ValidationError):
        GeoInfo.model_validate(raw_geo)


def test_geo_latitude_out_of_range_rejected(raw_geo):
    raw_geo["lat"] = 100.0  # 위도 -90~90 위반
    with pytest.raises(ValidationError):
        GeoInfo.model_validate(raw_geo)


# ── Open-Meteo 배열 평탄화 ────────────────────────────────────────────
def test_extract_weather_hours_flattens(raw_weather):
    rows = _extract_weather_hours(raw_weather)
    assert len(rows) == 2
    assert rows[0] == {
        "time": "2026-07-22T00:00",
        "temperature_2m": 24.9,
        "precipitation_probability": 100,
    }


def test_extract_weather_hours_length_mismatch(raw_weather):
    # 배열 길이 불일치 → 데이터 정합성 오류
    raw_weather["hourly"]["temperature_2m"] = [24.9]  # 1개만 (time은 2개)
    with pytest.raises(ValueError, match="길이가 일치하지 않습니다"):
        _extract_weather_hours(raw_weather)


# ── validate_all: 3종 통합 검증 ───────────────────────────────────────
def test_validate_all_ok(raw_weather, raw_country, raw_geo):
    raw = {"weather": raw_weather, "country": raw_country, "geo": raw_geo}
    data = validate_all(raw)
    assert len(data.weather) == 2
    assert data.country.alpha3Code == "KOR"
    assert data.geo.status == "success"


def test_validate_all_propagates_error(raw_weather, raw_country, raw_geo):
    # 한 곳이라도 검증 실패하면 전체가 예외 → 저장 단계로 안 넘어감
    raw_geo["lat"] = 999.0
    raw = {"weather": raw_weather, "country": raw_country, "geo": raw_geo}
    with pytest.raises(ValidationError):
        validate_all(raw)
