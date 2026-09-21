import asyncio
import httpx
from typing import Union
from uuid import uuid4

from fastapi import APIRouter, Depends, BackgroundTasks

from db.mongo import MongoDBManager
from db.mysql import MySQLManager
from db.redis import OCRCache
from models.schemas import OcrRequest, QuestionGenerationRequest
from nlp.llm import init_llm_model
from services.contract_analyzer import analyze_contract_parallel, generate_and_save_questions
from services.contract_parser import structure_contract_with_gpt
from services.decryption import DecryptionService
from services.legal_retriever import get_contract_type_requirements, get_clause_specific_laws_parallel
from services.ocr_engine import OcrEngine
from services.postprocessing import postprocessing_pipeline
from services.summarization import generate_summary
from utils.dependencies import (get_mongo, get_mysql, get_ocr_cache, get_vector_store,
                                get_decryption_service, get_ocr_engine,)
from utils.logging import setup_logger
from config.settings import WEBHOOK_API_KEY, SPRINGBOOT_WEBHOOK_URL

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

async def process_contract_background(
        job_id: str,
        req: Union[OcrRequest, QuestionGenerationRequest],
        decryption_service: DecryptionService,
        ocr_engine: OcrEngine,
        mysql: MySQLManager,
        mongo: MongoDBManager,
        ocr_cache: OCRCache,
        process_type: str = "ANALYSIS",
        vector_store = None,
        existing_data: dict = None,
):
    """백그라운드 처리 + 재시도 + 웹훅 통보 (질문 생성 / 분석 공용)"""
    cid = req.contract_id
    try:
        await process_contract_pipeline(
            req,
            decryption_service,
            ocr_engine,
            mysql,
            ocr_cache,
            mongo,
            process_type = process_type,
            vector_store = vector_store,
            existing_data = existing_data,
        )
        status = "completed"
    except Exception as e:
        logger.error(f"[{cid}] {process_type} 처리 오류: {e}", exc_info=True)
        if process_type == "ANALYSIS":
            await cleanup_incomplete_data(cid, mongo, mysql)
        status = "failed"

    await send_webhook_notification(
        job_id=job_id,
        contract_id=cid,
        contract_category_id=req.contract_category_id,
        status=status,
        result_type=process_type,
    )

async def process_contract_pipeline(
        req: Union[OcrRequest, QuestionGenerationRequest],
        decryption_service: DecryptionService,
        ocr_engine: OcrEngine,
        mysql: MySQLManager,
        ocr_cache: OCRCache,
        mongo: MongoDBManager,
        process_type: str = "ANALYSIS",
        vector_store = None,
        existing_data: dict = None
):
    """OCR → 요약 → 분석 파이프라인"""
    cid = req.contract_id
    cname = req.contract_category_name

    try:
        # 1. OCR 처리
        pages = await get_ocr_result(cid, decryption_service, ocr_engine, ocr_cache)
        all_text = "\n\n".join(p["cleaned_markdown"] for p in pages)

        llm = init_llm_model(temperature=0.0)

        if process_type == "QUESTION_GENERATION":
            # 질문 생성만 수행
            logger.info(f"[{cid}] 질문 생성만 수행")
            structured_contract = await structure_contract_with_gpt(all_text, cid, cname, llm)

            questions = await generate_and_save_questions(
                llm,
                structured_contract,
                req.contract_category_id,
                mysql,
                cname,
            )

            return {
                "success": True,
                "contract_id": cid,
                "question_count": len(questions),
                "question_completed": True
            }
        else :
            if mongo is None or vector_store is None or existing_data is None:
                raise ValueError("분석 모드에서는 mongo, vector_store, existing_data가 필요합니다.")
            # 2. AI 분석 보고서 ID 생성/가져오기
            if not existing_data['analysis']:
                ai_analysis_report_id = await mongo.save_ai_analysis_report(cid)
            else:
                report = await mongo.db.ai_analysis_report.find_one({"contractId": cid})
                ai_analysis_report_id = report["_id"]

            tasks = []

            # 3. 요약 생성
            if not existing_data['summary']:
                summary_task = lambda: generate_summary(all_text, cid, mongo)
                tasks.append(("summary", summary_task))


            # 4. 구조화 및 분석
            logger.info(f"[{cid}] 구조화 및 분석 시작")

            structured_contract_task = lambda: structure_contract_with_gpt(all_text, cid, cname, llm)
            tasks.append(("structure", structured_contract_task))

            results = await execute_parallel_tasks(tasks)

            summary_result = results.get("summary")
            structured_contract = results.get("structure")

            contract_type = structured_contract.metadata.contract_type
            # 5. MySQL에 조항 저장
            sections_data = []
            for section in structured_contract.sections:
                sections_data.append({
                    'number': section.number,
                    'title': section.title,
                    'content': section.content,
                    'type': section.type,
                })

            # 8. 구조화 완료 후 병렬 처리할 태스크들
            second_round_tasks = [
                ("mysql_save", lambda: mysql.save_contract_clauses(cid, sections_data)),
                ("summary_save",
                 lambda: mongo.save_summary_report(ai_analysis_report_id, summary_result) if summary_result else None),
                ("required_sections", lambda: get_contract_type_requirements(contract_type, cname, llm)),
                ("clause_laws", lambda: get_clause_specific_laws_parallel(structured_contract, vector_store))
            ]
            # None이 아닌 작업만 필터링
            second_round_tasks = [(name, task) for name, task in second_round_tasks if task is not None]

            second_results = await execute_parallel_tasks(second_round_tasks)

            required_sections = second_results.get("required_sections")
            clause_specific_laws = second_results.get("clause_laws")

            # 10. 최종 분석 (모든 준비가 완료된 후)
            logger.info(f"[{cid}] 최종 분석 시작")
            await analyze_contract_parallel(
                llm,
                structured_contract,
                req.contract_category_id,
                mongo,
                mysql,
                ai_analysis_report_id,
                required_sections,
                clause_specific_laws,
                contract_type,
                cname
            )

            logger.info(f"[{cid}] 전체 파이프라인 완료")
            return {
                "success": True,
                "contract_id": cid,
                "analysis_completed": True
            }

    except Exception as e:
        logger.error(f"[{cid}] 파이프라인 오류: {e}", exc_info=True)
        raise


async def execute_parallel_tasks(tasks, optional: set[str] = frozenset()):
    """병렬 태스크 실행 헬퍼 함수"""
    results = {}

    # 태스크 이름과 코루틴을 분리
    task_names = []
    coroutines = []

    for name, func  in tasks:
        if func is not None:
            task_names.append(name)
            coroutines.append(func())

    # 병렬 실행
    if coroutines:
        # 모든 작업을 동시에 실행
        task_results = await asyncio.gather(*coroutines, return_exceptions=True)

        # 병렬 처리 종료 시간
        # 결과 매핑
        for name, result in zip(task_names, task_results):
            if isinstance(result, Exception):
                if name in optional:
                    logger.warning(f"선택 태스크 {name} 실패, 없이 진행합니다: {result}")
                    results[name] = None
                    continue
                logger.error(f"Task {name} failed: {result}")
                raise result
            results[name] = result

    return results


async def check_existing_data(contract_id: int, mongo: MongoDBManager) -> dict:
    """기존 데이터 확인"""
    result = {
        'summary': False,
        'analysis': False
    }

    # 분석 및 요약 확인
    try:
        report = await mongo.db.ai_analysis_report.find_one({"contractId": contract_id})
        logger.info(f"[{contract_id}] : {report}")
        if report:
            result['analysis'] = True

            summary_doc = await mongo.db.summary_report.find_one(
                {"aiAnalysisReportId": report["_id"]}
            )
            logger.info(f"[{contract_id}] : {summary_doc}")
            result['summary'] = summary_doc is not None
    except Exception as e:
        logger.error(f"분석/요약 확인 오류: {e}")

    return result


# 헬퍼 함수들
async def get_ocr_result(cid, decryption_service, ocr_engine, ocr_cache):
    """OCR 결과 가져오기 (캐시 확인)"""
    cached_pages = await ocr_cache.get(cid)

    if cached_pages:
        logger.info(f"[{cid}] 캐시에서 OCR 결과 로드")
        return cached_pages

    logger.info(f"[{cid}] OCR 시작")
    pdf_bytes = await decryption_service.decrypt(cid)
    ocr_result = await ocr_engine.recognize(pdf_bytes)
    pages = postprocessing_pipeline(ocr_result, cid)

    # 캐시 저장 (실패해도 파이프라인은 계속 진행)
    try:
        await ocr_cache.set(cid, pages)
    except Exception as e:
        logger.warning(f"[{cid}] OCR 캐시 저장 실패, 계속 진행합니다: {e}")

    return pages


async def send_webhook_notification(
        job_id: str,
        contract_id: int,
        contract_category_id: int,
        status: str,
        result_type: str
):
    """Spring Boot에 웹훅 전송"""
    webhook_url = SPRINGBOOT_WEBHOOK_URL

    payload = {
        "contractId": contract_id,
        "contractCategoryId": contract_category_id,
        "status": status,
        "type": result_type
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": WEBHOOK_API_KEY  # 보안을 위한 API 키
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                webhook_url,
                json=payload,
                timeout=10.0,
                headers=headers
            )
            response.raise_for_status()
            logger.info(f"웹훅 전송 성공: {job_id}")
        except Exception as e:
            logger.error(f"웹훅 전송 실패: {e}")


# 정리 로직 함수 추가
async def cleanup_incomplete_data(contract_id, mongo, mysql):
    try:
        # 1. MongoDB에서 ai_analysis_report 찾기
        report = await mongo.db.ai_analysis_report.find_one({"contractId": contract_id})
        if report:
            report_id = report["_id"]

            # 2. 관련 서브 문서들 삭제
            for key in ("improvement_report", "missing_clause_report",
                        "risk_clause_report", "summary_report"):
                await mongo.delete_reports_by_analysis_id(report_id, key)

            # 3. 메인 리포트 삭제
            await mongo.db.ai_analysis_report.delete_one({"_id": report_id})

        # 4. MySQL 관련 데이터 정리
        async with mysql.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # 예: 질문 삭제
                await cur.execute("DELETE FROM question WHERE contract_id = %s", (contract_id,))
                # 예: clause 삭제
                await cur.execute("DELETE FROM clause WHERE contract_id = %s", (contract_id,))

        logger.info(f"계약서 ID {contract_id}의 불완전한 분석 데이터 정리 완료")
    except Exception as cleanup_error:
        logger.error(f"데이터 정리 중 오류 발생: {cleanup_error}", exc_info=True)