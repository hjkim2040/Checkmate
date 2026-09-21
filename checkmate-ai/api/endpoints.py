from uuid import uuid4

from fastapi import APIRouter, Depends, BackgroundTasks

from db.mongo import MongoDBManager
from db.mysql import MySQLManager
from db.redis import OCRCache
from models.schemas import OcrRequest, QuestionGenerationRequest
from services.contract_state import check_existing_data
from services.decryption import DecryptionService
from services.ocr_engine import OcrEngine
from services.pipeline import process_contract_background
from utils.dependencies import (
    get_mongo, get_mysql, get_ocr_cache, get_vector_store,
    get_decryption_service, get_ocr_engine,
)
from utils.logging import setup_logger

logger = setup_logger(__name__)
router = APIRouter()


@router.post("/questions/generate")
async def generate_questions_endpoint(
        req: QuestionGenerationRequest,
        background_tasks: BackgroundTasks,
        mysql: MySQLManager = Depends(get_mysql),
        mongo: MongoDBManager = Depends(get_mongo),
        ocr_cache: OCRCache = Depends(get_ocr_cache),
        decryption_service: DecryptionService = Depends(get_decryption_service),
        ocr_engine: OcrEngine = Depends(get_ocr_engine),
):
    """계약서 질문 생성 전용 엔드포인트"""

    # 작업 ID 생성
    job_id = str(uuid4())

    # 백그라운드 작업 추가
    background_tasks.add_task(
        process_contract_background,
        job_id=job_id,
        req=req,
        decryption_service=decryption_service,
        ocr_engine=ocr_engine,
        mysql=mysql,
        mongo=mongo,
        ocr_cache=ocr_cache,
        process_type="QUESTION_GENERATION",
    )

    # 즉시 응답
    return {
        "status": "processing",
        "message": "계약서 질문 생성이 시작되었습니다.",
        "job_id": job_id
    }

@router.post("/ocr")
async def ocr_endpoint(
        req: OcrRequest,
        background_tasks: BackgroundTasks,
        mysql: MySQLManager = Depends(get_mysql),
        mongo: MongoDBManager = Depends(get_mongo),
        vector_store=Depends(get_vector_store),
        ocr_cache: OCRCache = Depends(get_ocr_cache),
        decryption_service: DecryptionService = Depends(get_decryption_service),
        ocr_engine: OcrEngine = Depends(get_ocr_engine),
):
    """OCR → 요약 → 분석 통합 엔드포인트"""

    # 기존 데이터 확인
    existing_data = await check_existing_data(req.contract_id, mongo)
    logger.info(f'존재하는 데이터: {existing_data}')

    if existing_data['summary'] and existing_data['analysis']:
        return {
            "status": "completed",
            "detail": "이미 처리 완료된 계약서입니다.",
            "data": existing_data
        }

    # 작업 ID 생성
    job_id = str(uuid4())

    # 백그라운드 작업 추가
    background_tasks.add_task(
        process_contract_background,
        job_id=job_id,
        req=req,
        decryption_service=decryption_service,
        ocr_engine=ocr_engine,
        mysql=mysql,
        mongo=mongo,
        vector_store=vector_store,
        existing_data=existing_data,
        ocr_cache=ocr_cache,
        process_type="ANALYSIS",
    )

    # 즉시 응답
    return {
        "status": "processing",
        "message": "계약서 분석이 시작되었습니다. 잠시 후 결과를 확인해주세요.",
    }




