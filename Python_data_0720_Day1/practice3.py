import asyncio
import time

MAX_CONCURRENT = 10  # 동시 요청 상한(백프레셔)


# STEP 0. 동기 방식 — 하나씩 순서대로 대기 (느림)
def fetch_sync(item_id):
    time.sleep(0.1)  # 네트워크 대기를 흉내
    return {"id": item_id, "ok": True}


start = time.perf_counter()
sync_results = [fetch_sync(i) for i in range(60)]
print(f"동기: {time.perf_counter() - start:.2f}초")


# STEP 1~2. 기본 비동기 — gather로 60개를 동시에
async def fetch(item_id):
    await asyncio.sleep(0.1)  # time.sleep 아님! 반드시 asyncio.sleep
    return {"id": item_id, "ok": True}


async def run_basic_async():
    return await asyncio.gather(*[fetch(i) for i in range(60)])


start = time.perf_counter()
basic_results = asyncio.run(run_basic_async())
print(f"비동기: {time.perf_counter() - start:.2f}초")
print(f"기본 비동기 처리 건수: {len(basic_results)}건")


# STEP 3. Semaphore로 동시 요청 수 제한 (입장권 N장)
async def fetch_limited(item_id, sem):
    async with sem:  # 입장권 받기, 블록을 나가면 자동 반납
        await asyncio.sleep(0.1)
        return {"id": item_id, "ok": True}


async def run_limited_async():
    sem = asyncio.Semaphore(MAX_CONCURRENT)  # 실행 중인 루프에서 생성
    return await asyncio.gather(*[fetch_limited(i, sem) for i in range(60)])


start = time.perf_counter()
limited_results = asyncio.run(run_limited_async())
print(f"제한 비동기: {time.perf_counter() - start:.2f}초")
print(f"제한 비동기 처리 건수: {len(limited_results)}건")


# STEP 4. Timeout 적용 — 무한정 기다리지 않기
async def fetch_with_timeout(item_id, sem):
    async with sem:
        try:
            async with asyncio.timeout(3.0):  # 3초 넘으면 포기
                await asyncio.sleep(0.1)
                return {"id": item_id, "ok": True}
        except TimeoutError:
            return {"id": item_id, "ok": False, "reason": "timeout"}


async def run_timeout_test():
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    return await asyncio.gather(*[fetch_with_timeout(i, sem) for i in range(60)])


timeout_results = asyncio.run(run_timeout_test())
print(f"타임아웃 적용 처리 건수: {len(timeout_results)}건")


# STEP 5. 실제 요청 함수 — 15의 배수는 실패시켜 재시도 유도
async def do_request(item_id):
    await asyncio.sleep(0.1)
    if item_id != 0 and item_id % 15 == 0:
        raise RuntimeError("임시 네트워크 오류")
    return {"id": item_id, "ok": True}


# STEP 5. 지수 백오프 재시도 (1초 → 2초 → 4초)
async def fetch_retry(item_id, sem, max_retries=3):
    for attempt in range(max_retries):
        try:
            async with sem:
                return await do_request(item_id)
        except Exception as error:
            if attempt == max_retries - 1:  # 마지막 시도면 포기
                return {"id": item_id, "ok": False, "error": str(error)}
            wait = 2**attempt
            print(f"{item_id} 실패, {wait}초 후 재시도")
            await asyncio.sleep(wait)


# STEP 6. 예외 격리 — 하나 실패해도 전체는 살리기
async def run_retry_test():
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [fetch_retry(i, sem) for i in range(60)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    ok = [r for r in results if not isinstance(r, Exception)]
    fail = [r for r in results if isinstance(r, Exception)]
    print(f"성공 {len(ok)}건 / 예외 실패 {len(fail)}건")
    return results


retry_results = asyncio.run(run_retry_test())
retry_failed = [r for r in retry_results if isinstance(r, dict) and not r.get("ok", False)]
print(f"재시도 후 최종 실패: {len(retry_failed)}건")
