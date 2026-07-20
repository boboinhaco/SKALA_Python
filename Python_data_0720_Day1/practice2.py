import json

from pydantic import BaseModel, Field, ValidationError, field_validator


# STEP 0. JSON 데이터 확인
with open("data/api_response.json", encoding="utf-8") as file:
    raw_data = json.load(file)

# 최상위가 dict면 내부의 실제 리스트(results)를 꺼낸다.
if isinstance(raw_data, list):
    data = raw_data
elif isinstance(raw_data, dict):
    data = next((v for v in raw_data.values() if isinstance(v, list)), None)
    if data is None:
        raise ValueError("JSON 내부에서 데이터 리스트를 찾을 수 없습니다.")
else:
    raise TypeError("JSON 최상위 데이터 형식이 올바르지 않습니다.")

print("전체 건수:", len(data))  # 40
print("\n정상 샘플 1건")
print(json.dumps(data[0], indent=2, ensure_ascii=False))

# 앞 10건의 필드별 자료형 확인 (오염 지점 눈으로 찾기)
print("\n앞 10건의 필드별 자료형")
for index, row in enumerate(data[:10]):
    print(index, {key: type(value).__name__ for key, value in row.items()})


# STEP 1~4. Pydantic 중첩 스키마 정의
class Profile(BaseModel):
    # 안쪽 상자: 프로필 (score는 0~100 범위)
    country: str
    tier: str
    score: float = Field(ge=0, le=100)


class User(BaseModel):
    # 바깥 상자: 사용자
    id: int
    username: str
    email: str
    age: int = Field(ge=0)  # 음수 나이 거부
    is_active: bool
    signup_date: str
    profile: Profile
    tags: list[str] = Field(default_factory=list)

    # 이메일에 @가 있는지 확인하는 커스텀 규칙
    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("이메일 형식이 올바르지 않습니다.")
        return value


# 중첩 모델이 정상 변환되는지 확인
sample = User(
    id=1, username="tester", email="a@b.com", age=30, is_active=True,
    signup_date="2024-01-01", profile={"country": "KR", "tier": "pro", "score": 90},
)
print("\n중첩 모델 테스트")
print("국가:", sample.profile.country, "/ 점수:", sample.profile.score)


# STEP 5. 40건을 검증해 유효/오염 데이터로 분리 (실패해도 멈추지 않음)
valid: list[User] = []
invalid: list[dict] = []
for index, row in enumerate(data):
    try:
        valid.append(User.model_validate(row))
    except ValidationError as error:
        invalid.append({"index": index, "data": row, "errors": error.errors()})

print("\n" + "=" * 60)
print(f"전체 {len(data)}건 → 유효 {len(valid)}건 / 오염 {len(invalid)}건")


# STEP 6. 오염 데이터의 실패 사유 출력
print("\n" + "=" * 60)
print("오염 데이터 상세")
print("=" * 60)
print(f"{'행':<6}{'필드':<20}{'사유'}")
for item in invalid:
    for error in item["errors"]:
        field = ".".join(str(loc) for loc in error["loc"])
        print(f"{item['index']:<6}{field:<20}{error['msg']}")


# 성공 판정
assert len(data) == 40, "전체 데이터는 40건이어야 합니다."
assert len(valid) == 36, "유효 데이터는 36건이어야 합니다."
assert len(invalid) == 4, "오염 데이터는 4건이어야 합니다."
print("\n모든 Checkpoint를 통과했습니다.")
