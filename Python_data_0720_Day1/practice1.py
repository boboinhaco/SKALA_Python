import csv
from collections import Counter
from functools import reduce

# 1. 데이터 형태 확인
with open("data/web_logs.csv", encoding="utf-8") as f:
    for i, line in enumerate(f):
        print(line.strip())
        if i >= 4:
            break


# 2. 로그를 한 줄씩 읽는 제너레이터
def read_logs(path):
    # 한 줄씩 읽어 dict로 흘려보낸다.
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


# 3. 제너레이터 동작 확인
gen = read_logs("data/web_logs.csv")

for _ in range(3):
    print(next(gen))


# 4. 상태코드별 개수 확인
status_counter = Counter()
total = 0

for row in read_logs("data/web_logs.csv"):
    total += 1
    status_counter[row["status"]] += 1

print("총 건수:", total)
print(status_counter.most_common(5))


# 5. 전체 지표를 한 번에 집계
total = 0
by_status = Counter()
by_path = Counter()
by_hour = Counter()
by_ip = Counter()

for row in read_logs("data/web_logs.csv"):
    total += 1
    by_status[row["status"]] += 1
    by_path[row["path"]] += 1
    by_ip[row["ip"]] += 1

    hour = row["timestamp"][11:13]
    by_hour[hour] += 1


# 6. 5xx 오류율 계산
err_5xx = sum(
    count for status, count in by_status.items() if str(status).startswith("5")
)

ratio = err_5xx / total * 100

print(f"5xx: {err_5xx}건 ({ratio:.1f}%)")


# 7. reduce를 이용한 누적 집계
def fold(acc, row):
    # 누적기에 현재 행의 값을 반영한다.
    acc["total"] += 1
    acc["status"][row["status"]] += 1
    return acc


init = {
    "total": 0,
    "status": Counter(),
}

result = reduce(
    fold,
    read_logs("data/web_logs.csv"),
    init,
)

print(result["total"])


# 8. 최종 리포트 출력
print("=" * 40)
print(f"총 요청 수: {total:,}")
print(f"5xx 오류율: {ratio:.1f}%")

print("-- 인기 경로 TOP 5 --")
for path, count in by_path.most_common(5):
    print(f"{path:<20} {count:>7,}")

print("-- 접속 상위 IP TOP 5 --")
for ip, count in by_ip.most_common(5):
    print(f"{ip:<20} {count:>7,}")

import tracemalloc

print("\n=== 메모리 비교 ===")

# readlines() 방식 메모리 측정
tracemalloc.start()

with open("data/web_logs.csv", encoding="utf-8") as file:
    file.readlines()

_, peak = tracemalloc.get_traced_memory()
print(f"readlines 최대 메모리 : {peak / 1024 / 1024:.2f} MB")

tracemalloc.stop()

# 제너레이터 방식 메모리 측정
tracemalloc.start()

for _ in read_logs("data/web_logs.csv"):
    pass

_, peak = tracemalloc.get_traced_memory()
print(f"generator 최대 메모리 : {peak / 1024:.2f} KB")

tracemalloc.stop()
