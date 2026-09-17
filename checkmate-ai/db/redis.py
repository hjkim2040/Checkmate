import json
from typing import Optional

import redis.asyncio as redis

from config.settings import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, OCR_CACHE_TTL


class OCRCache:
    def __init__(self):
        self.redis = None
        self.pool = None

    async def connect(self):
        """Redis 연결"""
        self.pool = redis.ConnectionPool(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            max_connections=50,
            decode_responses=True
        )
        self.redis = await redis.Redis(connection_pool=self.pool)

    async def get(self, contract_id: int) -> Optional[dict]:
        """캐시에서 OCR 결과 가져오기"""
        if not self.redis:
            await self.connect()

        key = f"ocr:{contract_id}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set(self, contract_id: int, ocr_result: dict, expire: int = OCR_CACHE_TTL):
        """캐시에 OCR 결과 저장"""
        if not self.redis:
            await self.connect()

        key = f"ocr:{contract_id}"
        await self.redis.setex(key, expire, json.dumps(ocr_result))

    async def delete(self, contract_id: int):
        """캐시에서 특정 항목 삭제"""
        if not self.redis:
            await self.connect()

        key = f"ocr:{contract_id}"
        await self.redis.delete(key)

    async def close(self):
        """Redis 연결 종료"""
        if self.redis:
            await self.redis.close()
        if self.pool:
            await self.pool.disconnect()


