from concurrent.futures import ThreadPoolExecutor
from typing import Tuple, Any, List

import numpy as np
from huggingface_hub import InferenceClient
from langchain.embeddings.base import Embeddings

from config.settings import (
    EMBEDDING_REPO_ID, HUGGINGFACE_API_KEY
)
from utils.logging import setup_logger
from tenacity import retry, stop_after_attempt, wait_exponential

logger = setup_logger(__name__)


class HuggingFaceInferenceEmbeddings(Embeddings):
    """SentenceTransformer를 랩핑한 LangChain 호환 임베딩 클래스"""

    def __init__(self, client: InferenceClient, model: str):
        self.client = client
        self.model = model
        self.batch_size = 10

    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=1, min=1, max=5),
           reraise=True)
    def _embed_text_sync(self, text: str) -> List[float]:
        """동기 방식의 임베딩 생성 (API 호출)"""
        try:
            result = self.client.feature_extraction(
                text=text,
                model=self.model,
            )

            # numpy array 처리
            if isinstance(result, np.ndarray):
                if result.ndim > 1:
                    return result.mean(axis=0).tolist()
                else:
                    return result.tolist()
            elif isinstance(result[0], list):
                return result[0]
            else:
                return result
        except Exception as e:
            logger.error(f"임베딩 생성 오류 for text: {text[:50]}... - {e}")
            raise e

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """문서 리스트에 대한 임베딩 생성 (배치 처리)"""
        logger.info(f"총 {len(texts)}개 텍스트에 대한 배치 임베딩 생성 시작")

        # ThreadPoolExecutor를 사용한 병렬 처리
        embeddings = []

        with ThreadPoolExecutor(max_workers=self.batch_size) as executor:
            # 모든 텍스트에 대해 병렬로 임베딩 생성
            futures = [executor.submit(self._embed_text_sync, text) for text in texts]

            # 순서대로 결과 수집
            for i, future in enumerate(futures):
                try:
                    embedding = future.result()
                    embeddings.append(embedding)

                    # 진행 상황 로깅 (10개마다)
                    if (i + 1) % 10 == 0:
                        logger.info(f"진행률: {i + 1}/{len(texts)} ({(i + 1) * 100 / len(texts):.1f}%)")
                except Exception as e:
                    logger.error(f"텍스트 {i} 임베딩 생성 실패: {e}")
                    raise e

        logger.info(f"총 {len(embeddings)}개 임베딩 생성 완료")
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """단일 쿼리에 대한 임베딩 생성"""
        # 동기 방식으로 직접 처리
        return self._embed_text_sync(text)

def init_embedding_model() -> Tuple[Any, int]:
    """임베딩 모델 초기화"""

    try:
        api_key = HUGGINGFACE_API_KEY
        client = InferenceClient(
            provider="hf-inference",
            api_key=api_key,  # provider 대신 token 사용
        )

        model_name = EMBEDDING_REPO_ID


        # LangChain 호환 래퍼로 감싸기
        embeddings = HuggingFaceInferenceEmbeddings(client, model_name)

        # 테스트 임베딩 생성
        test_text = "차원 확인용 텍스트"
        test_embedding = embeddings.embed_query(test_text)
        embedding_dim = len(test_embedding)
        logger.info(f"hf 임베딩 모델 로드 성공 (차원: {embedding_dim})")

        return embeddings, embedding_dim

    except Exception as e:
        logger.error(f"임베딩 모델 로드 오류: {e}")
        raise
