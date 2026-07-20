import json

data = json.load(open('data/api_response.json', encoding='utf-8'))
print('전체건수:', len(data)) #40
print(json.dumps(data[0], indent=2, ensure_ascii=False)) # 정상샘플 1건

#어떤 키들이 있는지, 값 타입이 뭔지 확인
for i, row in enumerate(data[:10]):
    print(i, {k: type(v).__name__ for k, v in row.items()})

from pydantic import BaseModel

class Product(BaseModel):
    id: int # 이 이름의 필드가 잇고, 정수일 것
    name: str # 문자열일 것

# 테스트 : 정상 데이터
p = Product(id=1, name='사과')
print(p)

# 테스트 : 잘못된 데이터 > VaildationError 발생
try:
    Product(id='숫자아님', name='사과')
except Exception as e:
    print('걸림!', e)

from pydantic import BaseModel, Field
from typing import Annotated

class Product(BaseModel):
    id : int
    name : str
    price : float = Field(gt=0) # gt = grater than 0 (양수)
    quantity : int = Field(ge=0, le=10000) # 0이상 10000이하
# gt(초과) ge(이상) lt(미만) le(이하)

from pydantic import BaseModel, Field, field_validator

class Product(BaseModel):
    name: str
    category: str

    @field_validator('category')
    @classmethod
    def normalize_category(cls, v: str) -> str:
        v = v.strip().lower() # 앞뒤 공백 제거 > 소문자화
        if not v:
            raise ValueError('category 는 비어 있을 수 없습니다')
        return v # 반드시 값 return
    
from typing import List

class Seller(BaseModel): # 안쪽상자
    seller_id : int
    region: str

class Product(BaseModel): # 바깥상자
    id : int
    price : float = Field(gt=0)
    seller: Seller # 타입 자리에 다른 모델
    tags: List[str]=[] # 리스트도 각 원소까지 검사

# 중첩 dict를 넣으면 Pydantic 이 알아서 Seller로 변환+검증
p = Product(id=1, price=100, seller={'seller_id': 9, 'region': 'KR'})
print(p.seller.region)

from pydantic import ValidationError

vaild, invaild = [], []

for i, row in enumerate(data):
    try:
        vaild.append(Product(**row)) # 통과
    except ValidationError as e:
        invaild .append({
            'index' : i,
            'data' : row,
            'errors' : e.errors(),
        })

print(f'전체 {len(data)}건 -> 유효 {len(vaild)} / 오염 {len(invaild)}')
# 40건 -> 유효 36 / 오염 4가 나와야함

print(f" {'행': <4}{'필드': <12}{'사유'}")
for item in invaild:
    for err in item['errors']:
        field = '.' join(str(x) for x in err['loc']) # 중첩 경로 표시
print(f"{item['index']: <4} {field: <12} {err['msg']}")