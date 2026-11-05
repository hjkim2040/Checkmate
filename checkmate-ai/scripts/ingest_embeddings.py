import os
from typing import Tuple, Any

from langchain.embeddings.base import Embeddings
from sentence_transformers import SentenceTransformer

from config.settings import (
    EMBEDDING_REPO_ID,
)
from utils.logging import setup_logger

logger = setup_logger(__name__)


class SentenceTransformerEmbeddings(Embeddings):
    """SentenceTransformer를 랩핑한 LangChain 호환 임베딩 클래스"""

    def __init__(self, model: SentenceTransformer):
        self.model = model

    def embed_documents(self, texts):
        """문서 리스트에 대한 임베딩 생성"""
        return self.model.encode(texts).tolist()

    def embed_query(self, text):
        """단일 쿼리에 대한 임베딩 생성"""
        return self.model.encode([text])[0].tolist()


def init_embedding_model() -> Tuple[Any, int]:
    """임베딩 모델 초기화"""

    try:
        # 캐시 디렉토리
        os.environ['SENTENCE_TRANSFORMERS_HOME'] = os.path.join(os.getcwd(), "models", "sentence-transformers")

        model_name = EMBEDDING_REPO_ID

        model = SentenceTransformer(
            model_name
        )

        # LangChain 호환 래퍼로 감싸기
        embeddings = SentenceTransformerEmbeddings(model)

        # 테스트 임베딩 생성
        test_text = "차원 확인용 텍스트"
        test_embedding = embeddings.embed_query(test_text)
        embedding_dim = len(test_embedding)
        logger.info(f"SentenceTransformer  임베딩 모델 로드 성공 (차원: {embedding_dim})")

        return embeddings, embedding_dim

    except Exception as e:
        logger.error(f"임베딩 모델 로드 오류: {e}")
        raise
