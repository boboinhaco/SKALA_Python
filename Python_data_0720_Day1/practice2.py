import json

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    field_validator,
)


# STEP 0. JSON 데이터 확인
with open("data/api_response.json", encoding="utf-8") as file:
    raw_data = json.load(file)


# JSON 최상위 구조에서 실제 40건의 리스트를 가져온다.
if isinstance(raw_data, list):
    data = raw_data
elif isinstance(raw_data, dict):
    data = next(
        (
            value
            for value in raw_data.values()
            if isinstance(value, list)
        ),
        None,
    )

    if data is None:
        raise ValueError("JSON 내부에서 상품 데이터 리스트를 찾을 수 없습니다.")
else:
    raise TypeError("JSON 최상위 데이터 형식이 올바르지 않습니다.")


print("전체 건수:", len(data))  # 40

print("\n정상 샘플 1건")
print(
    json.dumps(
        data[0],
        indent=2,
        ensure_ascii=False,
    )
)

# 앞 10건의 필드명과 값의 자료형 확인
print("\n앞 10건의 필드별 자료형")

for index, row in enumerate(data[:10]):
    field_types = {
        key: type(value).__name__
        for key, value in row.items()
    }
    print(index, field_types)


# STEP 1~4. Pydantic 중첩 스키마 정의
class Seller(BaseModel):
    # 안쪽 상자: 판매자 정보
    seller_id: int
    region: str


class Product(BaseModel):
    # 바깥 상자: 상품 정보
    id: int
    name: str
    price: float = Field(gt=0)
    quantity: int = Field(ge=0, le=10000)
    category: str
    seller: Seller
    tags: list[str] = Field(default_factory=list)

    # category의 공백을 제거하고 소문자로 통일한다.
    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        value = value.strip().lower()

        if not value:
            raise ValueError("category는 비어 있을 수 없습니다.")

        return value


# 중첩 모델이 정상적으로 변환되는지 확인
sample = Product(
    id=1,
    name="사과",
    price=100,
    quantity=10,
    category=" Food ",
    seller={
        "seller_id": 9,
        "region": "KR",
    },
)

print("\n중첩 모델 테스트")
print("판매자 지역:", sample.seller.region)
print("정규화된 카테고리:", sample.category)


# STEP 5. 40건을 검증해 유효/오염 데이터로 분리
valid: list[Product] = []
invalid: list[dict] = []

for index, row in enumerate(data):
    try:
        valid.append(Product.model_validate(row))
    except ValidationError as error:
        invalid.append(
            {
                "index": index,
                "data": row,
                "errors": error.errors(),
            }
        )


print("\n" + "=" * 60)
print(
    f"전체 {len(data)}건 → "
    f"유효 {len(valid)}건 / "
    f"오염 {len(invalid)}건"
)


# STEP 6. 오염 데이터의 실패 사유 출력
print("\n" + "=" * 60)
print("오염 데이터 상세")
print("=" * 60)
print(f"{'행':<6}{'필드':<25}{'사유'}")

for item in invalid:
    for error in item["errors"]:
        field = ".".join(
            str(location)
            for location in error["loc"]
        )

        print(
            f"{item['index']:<6}"
            f"{field:<25}"
            f"{error['msg']}"
        )


# 성공 판정
assert len(data) == 40, "전체 데이터는 40건이어야 합니다."
assert len(valid) == 36, "유효 데이터는 36건이어야 합니다."
assert len(invalid) == 4, "오염 데이터는 4건이어야 합니다."

print("\n모든 Checkpoint를 통과했습니다.")