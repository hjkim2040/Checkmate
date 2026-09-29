from typing import List, Optional

from langchain.schema import Document
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.models import Distance, VectorParams

from config.settings import QDRANT_URL, QDRANT_API_KEY
from utils.logging import setup_logger

logger = setup_logger(__name__)


class QdrantDB:
    def __init__(self):
        self.async_client = None
        self.embeddings = None
        self.collection_name = None

    async def setup_collection(self, embeddings, embedding_dim: int, collection_name: str = "legal_documents"):
        """Qdrant 컬렉션 설정"""

        try:
            self.async_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
            self.embeddings = embeddings
            self.collection_name = collection_name

            # 컬렉션 존재 여부 확인
            collections = (await self.async_client.get_collections()).collections
            collection_names = [c.name for c in collections]

            if collection_name not in collection_names:
                # 컬렉션 생성
                await self.async_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=embedding_dim,
                        distance=Distance.COSINE
                    ),
                    optimizers_config=rest.OptimizersConfigDiff(
                        indexing_threshold=0
                    )
                )

                # 메타데이터 필드 인덱스 생성
                await self.async_client.create_payload_index(
                    collection_name=collection_name,
                    field_name="metadata.type",
                    field_schema=rest.PayloadSchemaType.KEYWORD
                )

                await self.async_client.create_payload_index(
                    collection_name=collection_name,
                    field_name="metadata.law_name",
                    field_schema=rest.PayloadSchemaType.KEYWORD
                )

                logger.info(f"컬렉션 '{collection_name}' 생성 완료")
            else:
                logger.info(f"컬렉션 '{collection_name}'이 이미 존재합니다")

            return collection_name

        except Exception as e:
            logger.error(f"Qdrant 설정 오류: {e}")
            raise

    @staticmethod
    def _to_document(point) -> Document:
        """Qdrant 포인트 → LangChain Document (langchain_qdrant 저장 형식 기준)"""
        payload = point.payload or {}
        return Document(
            page_content=payload.get("page_content", ""),
            metadata={**payload.get("metadata", {}), "score": point.score},
        )

    async def search_by_vectors(
            self,
            embeddings: List[List[float]],
            limit: int = 50,
            score_threshold: Optional[float] = None) -> List[List[Document]]:
        """여러 벡터를 한 번의 요청으로 검색. 결과 순서는 입력 순서와 같음"""
        if not embeddings:
            return []

        responses = await self.async_client.query_batch_points(
            collection_name=self.collection_name,
            requests=[
                rest.QueryRequest(query=embedding, limit=limit, score_threshold=score_threshold, with_payload=True)
                for embedding in embeddings
            ],
        )
        return [[self._to_document(p) for p in response.points] for response in responses]

    async def close(self):
        if self.async_client:
            await self.async_client.close()

# Qdrant 클라이언트 인스턴스 생성
qdrant_client = QdrantDB()
