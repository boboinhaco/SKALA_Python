import asyncio
import time


# STEP 0. 동기 방식
def fetch_sync(item_id):
    time.sleep(0.1)  # 네트워크 대기를 흉내
    return {"id": item_id, "ok": True}


start = time.perf_counter()

sync_results = [fetch_sync(i) for i in range(60)]

print(f"동기: {time.perf_counter() - start:.2f}초")


# STEP 1~2. 기본 비동기 방식
async def fetch(item_id):
    await asyncio.sleep(0.1)
    return {"id": item_id, "ok": True}


async def run_basic_async():
    tasks = [fetch(i) for i in range(60)]
    results = await asyncio.gather(*tasks)

    return results


start = time.perf_counter()

basic_results = asyncio.run(run_basic_async())

print(f"비동기: {time.perf_counter() - start:.2f}초")
print(f"기본 비동기 처리 건수: {len(basic_results)}건")


# STEP 3. Semaphore로 동시 요청 수 제한
MAX_CONCURRENT = 10
sem = asyncio.Semaphore(MAX_CONCURRENT)


async def fetch_limited(item_id):
    async with sem:  # 입장권 받기
        await asyncio.sleep(0.1)
        return {"id": item_id, "ok": True}
    # with 블록을 나가면 입장권 자동 반납


async def run_limited_async():
    tasks = [fetch_limited(i) for i in range(60)]
    results = await asyncio.gather(*tasks)

    return results


start = time.perf_counter()

limited_results = asyncio.run(run_limited_async())

print(f"제한 비동기: {time.perf_counter() - start:.2f}초")
print(f"제한 비동기 처리 건수: {len(limited_results)}건")


# STEP 4. Timeout 적용
async def fetch_with_timeout(item_id):
    async with sem:
        try:
            async with asyncio.timeout(3.0):  # 3초 넘으면 포기
                await asyncio.sleep(0.1)
                return {"id": item_id, "ok": True}
        except TimeoutError:
            return {
                "id": item_id,
                "ok": False,
                "reason": "timeout",
            }


async def run_timeout_test():
    tasks = [fetch_with_timeout(i) for i in range(60)]
    results = await asyncio.gather(*tasks)

    return results


timeout_results = asyncio.run(run_timeout_test())

print(f"타임아웃 적용 처리 건수: {len(timeout_results)}건")


# STEP 5. 재시도를 위한 실제 요청 함수
async def do_request(item_id):
    await asyncio.sleep(0.1)

    # 재시도 동작 확인용: 15의 배수는 실패하도록 설정
    if item_id != 0 and item_id % 15 == 0:
        raise RuntimeError("임시 네트워크 오류")

    return {"id": item_id, "ok": True}


# STEP 5. 지수 백오프 재시도
async def fetch_retry(item_id, max_retries=3):
    for attempt in range(max_retries):
        try:
            async with sem:
                return await do_request(item_id)

        except Exception as error:
            if attempt == max_retries - 1:
                return {
                    "id": item_id,
                    "ok": False,
                    "error": str(error),
                }

            wait = 2**attempt  # 1초 → 2초
            print(f"{item_id} 실패, {wait}초 후 재시도")

            await asyncio.sleep(wait)


# STEP 6. 예외 격리
async def run_retry_test():
    tasks = [fetch_retry(i) for i in range(60)]

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    ok = [
        result
        for result in results
        if not isinstance(result, Exception)
    ]

    fail = [
        result
        for result in results
        if isinstance(result, Exception)
    ]

    print(f"성공 {len(ok)}건 / 예외 실패 {len(fail)}건")

    return results


retry_results = asyncio.run(run_retry_test())

retry_failed = [
    result
    for result in retry_results
    if isinstance(result, dict) and not result.get("ok", False)
]

print(f"재시도 후 최종 실패: {len(retry_failed)}건")