"""
프로그램명: Advanced 3-1
전체 설명:
    비동기 요청 중 일부를 의도적으로 실패시키고,
    재시도 후에도 실패한 데이터를 dead_letter.json에 저장한다.
"""

import asyncio
import json
from pathlib import Path


MAX_CONCURRENT = 10
MAX_RETRIES = 3

sem = asyncio.Semaphore(MAX_CONCURRENT)

BASE_DIR = Path(__file__).resolve().parents[2]
DEAD_LETTER_FILE = Path(__file__).with_name("dead_letter.json")


# 일부 요청을 의도적으로 실패시키는 모의 요청 함수
async def do_request(item_id):
    await asyncio.sleep(0.1)

    # 15의 배수는 항상 실패하도록 설정
    if item_id != 0 and item_id % 15 == 0:
        raise RuntimeError("의도적으로 발생시킨 네트워크 오류")

    return {
        "id": item_id,
        "ok": True,
    }


# 실패 시 최대 3번까지 지수 백오프로 재시도
async def fetch_retry(item_id, max_retries=MAX_RETRIES):
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
                    "attempts": max_retries,
                }

            wait = 2**attempt
            print(f"{item_id}번 요청 실패, {wait}초 후 재시도")

            await asyncio.sleep(wait)


# 최종 실패 데이터를 JSON 파일로 저장
def save_dead_letters(dead_letters):
    DEAD_LETTER_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with DEAD_LETTER_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            dead_letters,
            file,
            ensure_ascii=False,
            indent=2,
        )


async def main():
    tasks = [
        fetch_retry(item_id)
        for item_id in range(60)
    ]

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    success = [
        result
        for result in results
        if isinstance(result, dict)
        and result.get("ok") is True
    ]

    dead_letters = [
        result
        for result in results
        if isinstance(result, dict)
        and result.get("ok") is False
    ]

    # 예상하지 못한 예외도 dead-letter 형태로 기록
    for result in results:
        if isinstance(result, Exception):
            dead_letters.append(
                {
                    "id": None,
                    "ok": False,
                    "error": str(result),
                }
            )

    save_dead_letters(dead_letters)

    print("=" * 50)
    print(f"전체 요청: {len(results)}건")
    print(f"성공: {len(success)}건")
    print(f"최종 실패: {len(dead_letters)}건")
    print(f"저장 파일: {DEAD_LETTER_FILE}")


if __name__ == "__main__":
    asyncio.run(main())