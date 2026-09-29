import logging
from typing import Optional

from config.settings import LLM_TIMEOUT_SECONDS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config.settings import OPENAI_API_KEY
from nlp.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class EmptySummaryError(Exception):
    pass

# 랭체인 모델 설정
llm = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0.0,
    api_key=OPENAI_API_KEY,
    max_tokens=2048,
    max_retries=2,
    timeout=LLM_TIMEOUT_SECONDS,
)

# 프롬프트 템플릿 설정
prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("user", USER_PROMPT_TEMPLATE)
])

# 요약 파이프라인 설정
summarization_chain = (
        prompt
        | llm
        | StrOutputParser()
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(EmptySummaryError),
    reraise=True
)
async def _generate_summary_with_retry(all_text: str) -> str:
    """LangChain과 retry 데코레이터를 이용한 요약 생성 함수"""
    try:
        # 텍스트 길이 제한 (10,000자)
        truncated_text = all_text[:10000]
        # summarization_chain 실행
        result = await summarization_chain.ainvoke(truncated_text)
        if not result or not result.strip():
            logger.error("빈 요약을 반환하여 재시도합니다.")
            raise EmptySummaryError("Empty Summary From LLM")
        return result
    except Exception as e:
        logger.error(f"요약 생성 중 오류 발생: {e}")
        raise


async def generate_summary(all_text: str, contract_id: int) -> Optional[str]:
    """
    전체 문서를 요약하고 결과를 반환합니다.
    DB에 이미 요약이 있다면 그것을 반환합니다.
    """
    try:
        logger.info(f"[{contract_id}] 새로운 요약 생성 시작")
        summary = await _generate_summary_with_retry(all_text)
        logger.info(f"[{contract_id}] 요약 생성 완료 (길이: {len(summary)})")
        return summary
    except Exception as e:
        logger.error(f"[{contract_id}] 요약 생성 실패: {e}", exc_info=True)
        # 기본 요약 반환
        return None


async def check_existing_summary(contract_id: int, mongo_db) -> str:
    """MongoDB에서 contract_id에 해당하는 기존 요약이 있는지 확인합니다."""
    try:
        # 1. ai_analysis_report에서 해당 contract_id의 문서 찾기
        report = await mongo_db.db.ai_analysis_report.find_one({"contractId": contract_id})
        if not report:
            return None

        # 2. summary_report에서 해당 ai_analysis_report_id의 요약 찾기
        summary_doc = await mongo_db.db.summary_report.find_one(
            {"aiAnalysisReportId": report["_id"]}
        )
        if not summary_doc:
            return None

        return summary_doc.get("description")
    except Exception as e:
        logger.error(f"기존 요약 확인 중 오류: {e}")
        return None
