import asyncio
import json
import re
from typing import Dict, Any, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from models.schemas import StructuredContract
from nlp.prompts import (
    missing_sections_prompt,
    improvements_prompt,
    risk_analysis_prompt,
    questions_generation_prompt
)
from utils.logging import setup_logger

# 빈 응답 예외 클래스
class EmptyResponseError(Exception):
    pass


logger = setup_logger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(EmptyResponseError),
    reraise=True
)
async def analyze_with_retry(llm, prompt_template, input_data: dict) -> dict:
    """LLM 호출 및 재시도 로직"""
    chain = prompt_template | llm

    result = await chain.ainvoke(input_data)
    # 결과 텍스트 추출
    if hasattr(result, 'content'):
        result_text = result.content
    else:
        result_text = str(result)

    # 빈 응답 체크
    if not result_text or not result_text.strip():
        logger.error("빈 응답을 받았습니다. 재시도합니다.")
        raise EmptyResponseError("Empty response from LLM")

    # JSON 파싱
    json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    json_match = re.search(json_pattern, result_text)

    try:
        if json_match:
            parsing_data = json.loads(json_match.group(1))
        else:
            parsing_data = json.loads(result_text.strip())
    except json.JSONDecodeError:
        logger.error("JSON 파싱 실패. 재시도합니다.")
        raise EmptyResponseError("Invalid JSON response")

    return parsing_data


async def analyze_contract_concur(
        llm,
        structured_contract: StructuredContract,
        contract_category_id: int,
        mongo_manager,
        mysql_manager,
        ai_analysis_report_id: str,
        required_sections: List[str],
        clause_specific_laws: Dict,
        contract_type: str,
        category_name: str,
) -> Dict[str, Any]:
    """계약서 전체를 분석하여 누락 조항, 개선 사항, 위험 영역 식별"""

    logger.info(f"계약서 분석 시작: {structured_contract.contract_id}")

    # 3. 법률 컨텍스트 포매팅
    legal_context = format_clause_laws(clause_specific_laws)

    # 필수 조항 목록을 텍스트로 변환
    required_sections_text = "\n".join([f"- {section}" for section in required_sections])

    # 계약서 전체 내용
    content = build_contract_content(structured_contract)

    # 공통 입력 데이터
    common_data = {
        "title": structured_contract.metadata.title,
        "contract_type": contract_type,
        "category_name": category_name,
        "content": content,
        "legal_context": legal_context
    }

    analysis_tasks = [
        # 1. 누락 조항 분석 (전체 필수 조항 정보 필요)
        ("missing", analyze_with_retry(llm, missing_sections_prompt, {
            **common_data,
            "required_sections": required_sections_text
        })),

        # 2. 개선사항 분석
        ("improvements", analyze_with_retry(llm, improvements_prompt, common_data)),

        # 3. 위험 조항 분석
        ("risks", analyze_with_retry(llm, risk_analysis_prompt, common_data)),

        # 4. 질문 생성
        ("questions", generate_questions(llm, structured_contract, category_name, content, contract_type))
    ]

    cid = structured_contract.contract_id

    try:
        responses = await asyncio.gather(*[task for _, task in analysis_tasks],
                                         return_exceptions=True)
        # 결과 매핑
        results = {}
        failed_tasks = []
        for (name, _), response in zip(analysis_tasks, responses):
            if isinstance(response, BaseException):
                logger.error(f"[{cid}] {name} 분석 실패: {response}", exc_info=response)
                failed_tasks.append(name)
            else:
                results[name] = response

        if failed_tasks:
            raise RuntimeError(f"[{cid}] 분석 태스크 실패: {failed_tasks}")

        # 각 분석 결과 저장
        await save_analysis_results(
            results,
            ai_analysis_report_id,
            structured_contract.contract_id,
            contract_category_id,
            mongo_manager,
            mysql_manager
        )

        logger.info(f"계약서 분석 완료: {structured_contract.contract_id}")

        return {
            "ai_analysis_report_id": str(ai_analysis_report_id),
            "analysis_completed": True,
            "failed_tasks": failed_tasks,
        }

    except Exception as e:
        logger.error(f"계약서 분석 오류: {e}")
        raise

def _excerpt(text: str, limit: int = 200) -> str:
    """조문을 limit 안의 마지막 문장 끝에서 자른다. 문장 끝이 없으면 limit에서 자른다."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = cut.rfind("다.")
    return (cut[:end + 2] if end > 0 else cut) + "..."

def format_clause_laws(clause_specific_laws: Dict) -> str:
    """조항별 법률 정보 포매팅"""
    if not clause_specific_laws:
        return "관련 법률 정보 없음"

    formatted = "=== 조항별 관련 법률 ===\n\n"

    for clause_num, clause_info in clause_specific_laws.items():
        formatted += f"{clause_num} - {clause_info['title']}\n"

        if clause_info.get('laws'):
            for law in clause_info['laws'][:2]:  # 각 조항당 최대 2개 법률만
                if hasattr(law, 'metadata'):
                    law_name = law.metadata.get('law_name', '알 수 없음')
                    article = law.metadata.get('article_number', '')
                    content = _excerpt(law.page_content if hasattr(law, 'page_content') else str(law))
                else:
                    law_name = "관련 법률"
                    article = ""
                    content = _excerpt(str(law))

                formatted += f"  • {law_name} {article}: {content}\n"
        else:
            formatted += "  • 관련 법률 없음\n"

        formatted += "\n"

    return formatted


async def save_analysis_results(
        results: Dict,
        ai_analysis_report_id: str,
        contract_id: int,
        contract_category_id: int,
        mongo_manager,
        mysql_manager
):
    """분석 결과를 DB에 저장"""

    # 성공한 유형만 기존 결과를 비우고 다시 쓴다.
    # 실패한 유형은 건드리지 않아 이전 성공분이 보존된다.
    collection_by_task = {
        "missing": "missing_clause_report",
        "improvements": "improvement_report",
        "risks": "risk_clause_report",
    }
    for task_name, collection_key in collection_by_task.items():
        if task_name not in results:
            continue
        deleted = await mongo_manager.delete_reports_by_analysis_id(
            ai_analysis_report_id, collection_key
        )
        if deleted:
            logger.info(f"[{contract_id}] {collection_key} 기존 {deleted}건 삭제 후 재저장")


    save_tasks = []

    # 1. 누락 조항 저장
    missing_sections = results.get("missing", {}).get("missing_sections", [])
    for item in missing_sections:
        save_tasks.append(mongo_manager.save_missing_clause_report(
            ai_analysis_report_id,
            item.get("severity", "중간"),
            item.get("description", "")
        ))

    # 2. 개선 사항 저장
    improvements = results.get("improvements", {}).get("improvement_recommendations", [])
    for item in improvements:
        save_tasks.append(mongo_manager.save_improvement_report(
            ai_analysis_report_id,
            item.get("description", "")
        ))

    # 3. 위험 영역 저장
    risk_clauses = results.get("risks", {}).get("risk_clauses", [])
    for item in risk_clauses:
        save_tasks.append(mongo_manager.save_risk_clause_report(
            ai_analysis_report_id,
            item.get("severity", "중간"),
            item.get("original_text", ""),
            item.get("description", "")
        ))

    # 4. 질문 저장
    questions_data = results.get("questions") or []

    failed = []
    batch_size = 10
    for i in range(0, len(save_tasks), batch_size):
        batch = save_tasks[i:i + batch_size]
        batch_results = await asyncio.gather(*batch, return_exceptions=True)

        # 에러 확인
        for idx, result in enumerate(batch_results):
            if isinstance(result, BaseException):
                logger.error(f"DB 저장 작업 {i + idx} 실패: {result!r}")
                failed.append(result)

    if failed:
        raise RuntimeError(
            f"[{contract_id}] 분석 결과 저장 실패: {len(failed)}/{len(save_tasks)}건"
        ) from failed[0]
    # MySQL 질문 배치 저장 (별도 처리)
    if questions_data:
        await mysql_manager.save_questions_batch(
            contract_id,
            contract_category_id,
            questions_data
        )

    logger.info(f"분석 결과 저장 완료")

def build_contract_content(
        structured_contract: StructuredContract,
) -> str:
    """구조화된 계약서를 LLM 입력용 단일 텍스트로 변환

    조항 조합 + 길이 제한 로직이 분석 파이프라인과 질문 생성 파이프라인
    양쪽에서 쓰이므로 여기 한 곳에서만 관리한다.
    """
    content = "\n\n".join(
        f"{section.number} {section.title}\n{section.content}"
        for section in structured_contract.sections
    )
    return content

async def generate_questions(
        llm,
        structured_contract: StructuredContract,
        category_name: str,
        content: Optional[str] = None,
        contract_type: Optional[str] = None
) -> List[Any]:
    """계약서 기반 질문 생성 (LLM 호출까지만 수행)

    :param content: 이미 만들어 둔 본문이 있으면 재사용 (중복 조합 방지)
    :param contract_type: 별도로 판별한 계약 유형이 있으면 우선 사용
    """
    if content is None:
        content = build_contract_content(structured_contract)

    questions_input = {
        "title": structured_contract.metadata.title,
        "contract_type": contract_type or structured_contract.metadata.contract_type,
        "category_name": category_name,
        "content": content,
    }

    response = await analyze_with_retry(llm, questions_generation_prompt, questions_input)
    return response.get("questions", [])

async def generate_and_save_questions(
        llm,
        structured_contract: StructuredContract,
        contract_category_id: int,
        mysql_manager,
        category_name: str,
        content: Optional[str] = None,
        contract_type: Optional[str] = None
) -> List[Any]:
    """질문 생성 후 MySQL 저장까지 수행 (질문 생성 전용 파이프라인용)"""
    cid = structured_contract.contract_id

    questions = await generate_questions(llm, structured_contract, category_name, content, contract_type)

    if questions:
        await mysql_manager.save_questions_batch(cid, contract_category_id, questions)

    logger.info(f"[{cid}] 질문 생성 완료: {len(questions)}개 생성됨")
    return questions