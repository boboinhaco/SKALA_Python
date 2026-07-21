"""schema.py — 수집 JSON 스키마 검증 (Pydantic v2)

[프로그램 설명]
    [Day 1] 종합 실습 "데이터 수집 미니 파이프라인"의 2단계.
    collect.py가 수집한 원본 JSON에서 "필요한 필드만 추출"하고,
    Pydantic v2 모델로 타입과 값의 범위(기온·확률·위경도 등)를 검증한다.
    검증에 실패하면 ValidationError를 발생시켜 잘못된 데이터가 저장 단계로
    넘어가지 않도록 막는다.

[검증 대상 3종]
    - WeatherHour : Open-Meteo 시간대별 기온·강수확률 (배열 → 시간별 레코드로 평탄화)
    - CountryInfo : Countries.dev 한국 국가 정보
    - GeoInfo     : ip-api IP 기반 지역 정보

[변경 내역]
    2026-07-21  최초 작성 — Pydantic v2 모델 3종 + validate_all()
"""

from __future__ import annotations

from pydantic import BaseModel, Field, TypeAdapter, field_validator


# ─────────────────────────────────────────────────────────────
# 1) Open-Meteo — 시간대별 기온·강수확률
# ─────────────────────────────────────────────────────────────
class WeatherHour(BaseModel):
    """서울 특정 시각의 기온·강수확률 1건.

    - temperature_2m: 지표 기온(°C). 지구 관측 범위를 벗어나면 이상치로 간주.
    - precipitation_probability: 강수확률(%). 0~100 범위만 허용.
    """

    time: str = Field(min_length=1)  # ISO8601 문자열 (예: 2026-07-21T00:00)
    temperature_2m: float = Field(ge=-90.0, le=60.0)
    precipitation_probability: int = Field(ge=0, le=100)


# ─────────────────────────────────────────────────────────────
# 2) Countries.dev — 한국 국가 정보
# ─────────────────────────────────────────────────────────────
class CountryInfo(BaseModel):
    """국가 요약 정보 (한국)."""

    name: str = Field(min_length=1)
    alpha3Code: str = Field(min_length=3, max_length=3)  # KOR
    region: str = Field(min_length=1)
    capital: str = Field(min_length=1)
    population: int = Field(gt=0)
    area: float = Field(gt=0)

    @field_validator("alpha3Code")
    @classmethod
    def _upper_alpha3(cls, v: str) -> str:
        # 국가 코드는 대문자로 정규화 (kor → KOR)
        return v.upper()


# ─────────────────────────────────────────────────────────────
# 3) ip-api — IP 기반 지역 정보
# ─────────────────────────────────────────────────────────────
class GeoInfo(BaseModel):
    """IP 기반 위치 정보."""

    status: str = Field(min_length=1)
    country: str = Field(min_length=1)
    countryCode: str = Field(min_length=2, max_length=2)  # US, KR ...
    regionName: str = Field(min_length=1)
    city: str = Field(min_length=1)
    lat: float = Field(ge=-90.0, le=90.0)  # 위도 범위
    lon: float = Field(ge=-180.0, le=180.0)  # 경도 범위
    timezone: str = Field(min_length=1)
    query: str = Field(min_length=1)  # 조회한 IP

    @field_validator("status")
    @classmethod
    def _must_be_success(cls, v: str) -> str:
        # ip-api는 실패 시 status="fail" 을 반환 → 성공 응답만 통과
        if v != "success":
            raise ValueError(f"ip-api 응답 실패: status={v!r}")
        return v


# 시간별 배열 → WeatherHour 리스트 검증용 어댑터
_WEATHER_ADAPTER = TypeAdapter(list[WeatherHour])


def _extract_weather_hours(payload: dict) -> list[dict]:
    """Open-Meteo의 병렬 배열(hourly)을 시간별 레코드 리스트로 평탄화.

    { time:[...], temperature_2m:[...], precipitation_probability:[...] }
      → [ {time, temperature_2m, precipitation_probability}, ... ]
    세 배열의 길이가 다르면 데이터 정합성 오류로 간주해 예외 발생.
    """
    hourly = payload["hourly"]
    times = hourly["time"]
    temps = hourly["temperature_2m"]
    probs = hourly["precipitation_probability"]
    if not (len(times) == len(temps) == len(probs)):
        raise ValueError("Open-Meteo hourly 배열 길이가 일치하지 않습니다")
    return [
        {"time": t, "temperature_2m": temp, "precipitation_probability": prob}
        for t, temp, prob in zip(times, temps, probs, strict=False)
    ]


class ValidatedData(BaseModel):
    """검증을 통과한 3종 데이터 묶음 (저장 단계로 전달)."""

    weather: list[WeatherHour]
    country: CountryInfo
    geo: GeoInfo


def validate_all(raw: dict[str, dict]) -> ValidatedData:
    """collect_all()의 원본 JSON을 받아 3종 모델로 검증한 결과를 반환.

    - 필요한 필드만 추출 후 각 모델이 타입·범위를 검증.
    - 하나라도 어긋나면 pydantic.ValidationError(또는 ValueError) 발생.
    """
    weather = _WEATHER_ADAPTER.validate_python(_extract_weather_hours(raw["weather"]))
    country = CountryInfo.model_validate(raw["country"])
    geo = GeoInfo.model_validate(raw["geo"])
    return ValidatedData(weather=weather, country=country, geo=geo)
