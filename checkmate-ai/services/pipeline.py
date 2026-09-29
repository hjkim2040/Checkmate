import asyncio
from typing import Union
from collections.abc import Collection

from db.mongo import MongoDBManager, SUMMARY_FAILED_MESSAGE
from db.mysql import MySQLManager
from db.redis import OCRCache
from models.schemas import OcrRequest, QuestionGenerationRequest
from nlp.llm import init_llm_model
from services.contract_analyzer import analyze_contract_concur, generate_and_save_questions
from services.contract_parser import structure_contract_with_gpt
from services.contract_state import cleanup_incomplete_data
from services.decryption import DecryptionService
from services.legal_retriever import get_contract_type_requirements, get_clause_specific_laws_parallel
from services.ocr_engine import OcrEngine
from services.postprocessing import postprocessing_pipeline
from services.summarization import generate_summary
from services.webhook import send_webhook_notification
from utils.logging import setup_logger

logger = setup_logger(__name__)

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
        pages = await _get_ocr_result(cid, decryption_service, ocr_engine, ocr_cache)
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
                report = await mongo.find_report_by_contract_id(cid)
                ai_analysis_report_id = report["_id"]

            tasks = []

            # 3. 요약 생성
            if not existing_data['summary']:
                summary_task = lambda: generate_summary(all_text, cid)
                tasks.append(("summary", summary_task))


            # 4. 구조화 및 분석
            logger.info(f"[{cid}] 구조화 및 분석 시작")

            structured_contract_task = lambda: structure_contract_with_gpt(all_text, cid, cname, llm)
            tasks.append(("structure", structured_contract_task))

            results = await _execute_parallel_tasks(tasks)

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
                ("required_sections", lambda: get_contract_type_requirements(contract_type, cname, llm)),
                ("clause_laws", lambda: get_clause_specific_laws_parallel(structured_contract, vector_store))
            ]
            if "summary" in results:
                if summary_result:
                    save_summary = lambda: mongo.save_summary_report(ai_analysis_report_id, summary_result)
                else:
                    save_summary = lambda: mongo.save_summary_report(
                        ai_analysis_report_id, SUMMARY_FAILED_MESSAGE, generation_failed=True
                    )
                second_round_tasks.append(
                    ("summary_save", save_summary),
                )

            second_results = await _execute_parallel_tasks(
                second_round_tasks,
                optional={"required_sections", "clause_laws"})

            required_sections = second_results.get("required_sections") or []
            clause_specific_laws = second_results.get("clause_laws") or {}

            # 10. 최종 분석 (모든 준비가 완료된 후)
            logger.info(f"[{cid}] 최종 분석 시작")
            await analyze_contract_concur(
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


async def _execute_parallel_tasks(tasks, optional: Collection[str] = frozenset()):
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

async def _get_ocr_result(cid, decryption_service, ocr_engine, ocr_cache):
    """OCR 결과 가져오기 (캐시 확인)"""
    cached_pages = await ocr_cache.get(cid)

    if cached_pages:
        logger.info(f"[{cid}] 캐시에서 OCR 결과 로드")
        return cached_pages

    logger.info(f"[{cid}] OCR 시작")
    pdf_bytes = await decryption_service.decrypt(cid)
    ocr_result = await ocr_engine.recognize(pdf_bytes)
    pages = await asyncio.to_thread(postprocessing_pipeline, ocr_result, cid)

    # 캐시 저장 (실패해도 파이프라인은 계속 진행)
    try:
        await ocr_cache.set(cid, pages)
    except Exception as e:
        logger.warning(f"[{cid}] OCR 캐시 저장 실패, 계속 진행합니다: {e}")

    return pages