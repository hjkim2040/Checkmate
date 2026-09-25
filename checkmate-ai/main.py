from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.endpoints import router
from db.qdrant import qdrant_client
from nlp.embeddings import init_embedding_model
from utils.dependencies import ocr_cache, mysql_manager, mongo_manager
from utils.logging import setup_logger

# 로깅 설정
logger = setup_logger(__name__)

async def _safe_close(name: str, close_fn) -> None:
    """종료 작업 하나가 실패해도 나머지는 계속 진행"""
    try:
        await close_fn()
        logger.info(f"{name} 종료 완료")
    except Exception as e:
        logger.error(f"{name} 종료 중 오류: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("애플리케이션 시작 - DB 연결 초기화")
    try:
        # MySQL 연결
        await mysql_manager.connect()

        # MongoDB 연결
        await mongo_manager.connect()

        # Redis 캐시 연결 (추가)
        await ocr_cache.connect()
        logger.info("Redis 캐시 연결 완료")

        # Qdrant 초기화
        embeddings, embedding_dim = await init_embedding_model()
        await qdrant_client.setup_collection(embeddings, embedding_dim)

        # 벡터 스토어 상태 확인
        count = await qdrant_client.async_client.count(
            collection_name=qdrant_client.collection_name,
            exact=True
        )
        logger.info(f"벡터 DB 내 법률 문서 수: {count.count}")
        logger.info("모든 DB 연결 완료")
    except Exception as e:
        logger.error(f"DB 초기화 실패: {e}")
        raise

    yield

    # Shutdown
    logger.info("애플리케이션 종료 - DB 연결 해제")
    await _safe_close("MySQL", mysql_manager.disconnect)
    await _safe_close("MongoDB", mongo_manager.disconnect)
    await _safe_close("Redis", ocr_cache.close)
    await _safe_close("Qdrant", qdrant_client.close)
    if qdrant_client.embeddings:
        await _safe_close("HF 임베딩", qdrant_client.embeddings.aclose)


# FastAPI 앱 초기화
app = FastAPI(
    title="계약서 분석 및 검토 API",
    description="계약서 작성 및 검토를 도와주는 AI 기반 서비스 API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 운영 환경에서는 구체적인 오리진 지정 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(router, prefix="/api", tags=["contract"])

