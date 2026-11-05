import glob
import json
import os
from typing import List, Dict

from scripts.ingest_qdrant import qdrant_client
from scripts.ingest_embeddings import init_embedding_model
from utils.logging import setup_logger

logger = setup_logger(__name__)


class LegalDocumentsProcessor:
    """법률 문서를 자동으로 처리하는 클래스"""

    def __init__(self, documents_folder: str = "data/legal_documents"):
        self.documents_folder = documents_folder
        self.all_documents = []

    def load_all_json_files(self) -> List[Dict[str, str]]:
        """지정된 폴더의 모든 JSON 파일을 로드"""

        # JSON 파일 경로 패턴
        json_pattern = os.path.join(self.documents_folder, "*.json")
        json_files = glob.glob(json_pattern)

        logger.info(f"{self.documents_folder} 폴더에서 {len(json_files)}개의 JSON 파일 발견")

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    documents = json.load(f)

                    # 파일이 리스트인지 확인
                    if isinstance(documents, list):
                        self.all_documents.extend(documents)
                        logger.info(f"{json_file}에서 {len(documents)}개 문서 로드")
                    else:
                        logger.warning(f"{json_file}은 리스트 형식이 아님")

            except Exception as e:
                logger.error(f"{json_file} 로드 중 오류: {e}")

        logger.info(f"총 {len(self.all_documents)}개 법률 문서 로드 완료")
        return self.all_documents

    def process_and_store_documents(self):
        """문서를 로드하고 벡터 DB에 저장"""

        # 1. 모든 JSON 파일 로드
        documents = self.all_documents or self.load_all_json_files()

        if not documents:
            logger.warning("로드된 문서가 없습니다")
            return

        # 2. 임베딩 모델 초기화
        embeddings, embedding_dim = init_embedding_model()

        # 3. Qdrant 컬렉션 설정
        collection_name = qdrant_client.setup_collection(embedding_dim)

        # 4. 벡터 저장소 설정
        qdrant_client.setup_vector_store(embeddings, collection_name)

        # 5. 법률 문서 저장
        qdrant_client.store_legal_documents(documents)

    def validate_documents(self) -> bool:
        """문서 형식 검증"""

        required_fields = ["content", "title", "type", "law_name"]
        is_valid = True

        for idx, doc in enumerate(self.all_documents):
            missing_fields = []

            for field in required_fields:
                if field not in doc:
                    missing_fields.append(field)

            if missing_fields:
                logger.error(f"문서 {idx}에 필수 필드 누락: {missing_fields}")
                is_valid = False

        return is_valid


# 실행 스크립트
def main():
    """메인 실행 함수"""

    import argparse

    parser = argparse.ArgumentParser(description="법률 문서 자동 로더")
    parser.add_argument(
        "--folder",
        default="data/legal_documents",
        help="법률 문서 JSON 파일이 있는 폴더 경로"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="문서 검증만 수행"
    )

    args = parser.parse_args()

    # 프로세서 초기화
    processor = LegalDocumentsProcessor(args.folder)

    # 모든 파일 로드
    processor.load_all_json_files()

    # 문서 검증
    if processor.validate_documents():
        logger.info("모든 문서가 올바른 형식입니다")

        if args.validate_only:
            return

        # 벡터 DB에 저장
        if not args.validate_only:
            processor.process_and_store_documents()
    else:
        logger.error("문서 형식 검증 실패")


if __name__ == "__main__":
    main()
