from typing import List, Dict

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.models import Distance, VectorParams

from config.settings import QDRANT_URL, QDRANT_API_KEY
from utils.logging import setup_logger

logger = setup_logger(__name__)


class QdrantDB:
    def __init__(self):
        self.client = None
        self.vector_store = None

    def setup_collection(self, embedding_dim: int, collection_name: str = "legal_documents"):
        """Qdrant 컬렉션 설정"""

        try:
            self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

            # 컬렉션 존재 여부 확인
            collections = self.client.get_collections().collections
            collection_names = [collection.name for collection in collections]

            if collection_name not in collection_names:
                # 컬렉션 생성
                self.client.create_collection(
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
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="metadata.type",
                    field_schema=rest.PayloadSchemaType.KEYWORD
                )

                self.client.create_payload_index(
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

    def setup_vector_store(self, embeddings, collection_name: str):
        """Qdrant 벡터 저장소 설정"""

        try:
            # API 키가 있는 경우
            if QDRANT_API_KEY:
                self.vector_store = QdrantVectorStore(
                    client=self.client,  # 이미 인증된 client 사용
                    collection_name=collection_name,
                    embedding=embeddings
                )

            logger.info("벡터 저장소 설정 완료")
            return self.vector_store

        except Exception as e:
            logger.error(f"벡터 저장소 설정 오류: {e}")
            raise

    def store_legal_documents(self, legal_texts: List[Dict[str, str]]):
        """법률 문서를 벡터 저장소에 저장"""

        logger.info(f"법률 문서 {len(legal_texts)}개 저장 중...")

        # 문서 분할기
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", " "]
        )

        total_chunks = 0
        all_documents = []

        for legal_doc in legal_texts:
            # 문서를 청크로 분할
            chunks = text_splitter.split_text(legal_doc["content"])
            total_chunks += len(chunks)

            # Document 객체 생성
            documents = [
                Document(
                    page_content=chunk,
                    metadata={
                        "title": legal_doc["title"],
                        "type": legal_doc["type"],
                        "law_name": legal_doc.get("law_name", ""),
                        "article_number": legal_doc.get("article_number", "")
                    }
                )
                for chunk in chunks
            ]
            all_documents.extend(documents)

        # 벡터 저장소에 추가
        self.vector_store.add_documents(all_documents)

        logger.info(f"총 {len(legal_texts)}개 법률 문서, {total_chunks}개 청크 저장 완료")

    def get_vector_store(self):
        """벡터 스토어 반환"""
        return self.vector_store


# Qdrant 클라이언트 인스턴스 생성
qdrant_client = QdrantDB()
