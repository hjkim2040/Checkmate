import asyncio
from typing import Tuple, Any, List

import numpy as np
from huggingface_hub import AsyncInferenceClient

from config.settings import (
    EMBEDDING_REPO_ID, HUGGINGFACE_API_KEY
)
from utils.logging import setup_logger
from tenacity import retry, stop_after_attempt, wait_exponential

logger = setup_logger(__name__)


class HuggingFaceEmbedder:

    def __init__(self, async_client, model: str, max_concurrency=10):
        self.async_client = async_client
        self.model = model
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @staticmethod
    def _to_vector(result) -> List[float]:
        if isinstance(result, np.ndarray):
            return result.mean(axis=0).tolist() if result.ndim > 1 else result.tolist()
        return result[0] if isinstance(result[0], list) else result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
    async def _embed_text_async(self, text: str) -> List[float]:
        async with self._semaphore:
            result = await self.async_client.feature_extraction(text=text, model=self.model)
        return self._to_vector(result)

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return list(await asyncio.gather(*(self._embed_text_async(t) for t in texts)))

    async def embed_query(self, text: str) -> List[float]:
        return await self._embed_text_async(text)

    async def aclose(self):
        await self.async_client.close()

async def init_embedding_model() -> Tuple[Any, int]:
    """임베딩 모델 초기화"""

    try:
        api_key = HUGGINGFACE_API_KEY
        async_client = AsyncInferenceClient(
            provider="hf-inference",
            api_key=api_key,
        )
        model_name = EMBEDDING_REPO_ID

        embeddings = HuggingFaceEmbedder(async_client, model_name)

        # 테스트 임베딩 생성
        test_text = "차원 확인용 텍스트"
        embedding_dim = len(await embeddings.embed_query(test_text))
        logger.info(f"hf 임베딩 모델 로드 성공 (차원: {embedding_dim})")

        return embeddings, embedding_dim

    except Exception as e:
        logger.error(f"임베딩 모델 로드 오류: {e}")
        raise
