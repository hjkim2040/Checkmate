from db.mongo import MongoDBManager
from db.mysql import MySQLManager
from db.redis import OCRCache
from db.qdrant import qdrant_client
from services.decryption import DecryptionService
from services.ocr_engine import OcrEngine

# 전역 인스턴스 생성
mysql_manager = MySQLManager()
mongo_manager = MongoDBManager()
ocr_cache = OCRCache()
decryption_service = DecryptionService(mysql_manager, mongo_manager)
ocr_engine = OcrEngine()


async def get_mysql() -> MySQLManager:
    """MySQL 의존성"""
    return mysql_manager


async def get_mongo() -> MongoDBManager:
    """MongoDB 의존성"""
    return mongo_manager


async def get_ocr_cache() -> OCRCache:
    """Redis 캐시 의존성"""
    return ocr_cache


async def get_vector_store():
    """Qdrant 의존성 (임베딩 + 비동기 검색)"""
    if qdrant_client.async_client is None or qdrant_client.embeddings is None:
        raise ValueError("Vector store가 초기화되지 않았습니다. 서버가 완전히 시작될 때까지 기다려주세요.")
    return qdrant_client

async def get_decryption_service() -> DecryptionService:
    """복호화 서비스 의존성"""
    return decryption_service


async def get_ocr_engine() -> OcrEngine:
    """OCR 엔진 의존성"""
    return ocr_engine