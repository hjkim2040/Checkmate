import json
import random
import re
import asyncio
from datetime import datetime

from models.schemas import StructuredContract
from nlp.llm import init_llm_model
from nlp.prompts import contract_structuring_chat_prompt
from utils.logging import setup_logger

logger = setup_logger(__name__)


# 빈 응답 예외 클래스
class EmptyStructureError(Exception):
    pass


async def structure_contract_with_gpt(contract_text: str, contract_id: int = None, category_name = None, llm=None) -> StructuredContract:
    """OpenAI GPT-4를 이용한 계약서 구조화"""

    if contract_id is None:
        contract_id = int(datetime.now().timestamp())

    logger.info(f"[{contract_id}] 계약서 구조화 시작")

    # 재시도 설정
    MAX_RETRIES = 3

    # GPT-4 모델 초기화
    if llm is None:
        llm = init_llm_model(temperature=0.0)

    last_exception = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # 일반적인 경우: 전체 텍스트 한 번에 처리
            result = await process_single_chunk(llm, contract_text, category_name)

            # 응답 검증
            validate_structure_response(result)

            # 구조화된 계약서 객체 생성
            contract_data = {
                "contract_id": contract_id,
                "metadata": {
                    "title": result.get("title", ""),
                    "date": result.get("date", ""),
                    "parties": result.get("parties", []),
                    "contract_type": result.get("contract_type", "general_contract")
                },
                "sections": [
                    {
                        "number": section.get("number", ""),
                        "title": section.get("title", ""),
                        "content": section.get("content", ""),
                        "type": section.get("type", "unknown")
                    }
                    for section in result.get("sections", [])
                ]
            }
            logger.info(f"[{contract_id}] 계약서 구조화 완료")
            return StructuredContract(**contract_data)


        except (EmptyStructureError, json.JSONDecodeError) as e:
            last_exception = e
            if attempt < MAX_RETRIES:
                # 지수 백오프 + 약간의 무작위성
                backoff_time = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"시도 {attempt}/{MAX_RETRIES} 실패: {e}. {backoff_time:.2f}초 후 재시도...")
                await asyncio.sleep(backoff_time)
            else:
                logger.error(f"모든 시도 실패. 최종 오류: {e}")
    # 최대 시도 횟수 초과 시 예외 다시 발생
    raise last_exception


async def process_single_chunk(llm, contract_text, category_name):
    """단일 청크 계약서 처리"""
    # 프롬프트 체인 실행
    chain = contract_structuring_chat_prompt | llm
    result = await chain.ainvoke({"contract_text": contract_text, "category_name": category_name})

    # JSON 파싱
    # ChatOpenAI는 AIMessage 객체를 반환하므로 content 추출
    if hasattr(result, 'content'):
        result_text = result.content
    else:
        result_text = str(result)

    # 빈 응답 체크
    if not result_text or not result_text.strip():
        raise EmptyStructureError("빈 응답을 받았습니다")

    # JSON 추출을 위한 정규식 패턴
    json_pattern = r'```(?:json)?\n([\s\S]*?)\n```'
    json_match = re.search(json_pattern, result_text)

    try:
        if json_match:
            return json.loads(json_match.group(1))
        else:
            # 백틱이 없는 경우 전체 텍스트를 JSON으로 시도
            return json.loads(result_text.strip())
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 오류: {e}")
        raise EmptyStructureError(f"유효한 JSON 응답이 아닙니다: {e}")


def validate_structure_response(result: dict):
    """구조화 응답 검증"""
    if not result:
        raise EmptyStructureError("빈 결과를 받았습니다")

    # 필수 필드 확인
    required_fields = ["title", "date", "parties", "contract_type", "sections"]
    missing_fields = [field for field in required_fields if field not in result]

    if missing_fields:
        raise EmptyStructureError(f"필수 필드가 누락되었습니다: {missing_fields}")

    # sections 비어있는지 확인
    if not result.get("sections"):
        raise EmptyStructureError("계약서 조항(sections)이 비어있습니다")

    # 각 section에 필수 필드가 있는지 확인
    for i, section in enumerate(result.get("sections", [])):
        if not section.get("content"):
            raise EmptyStructureError(f"조항 {i}의 내용(content)이 비어있습니다")

    # parties가 비어있는지 확인
    if not result.get("parties"):
        raise EmptyStructureError("계약 당사자(parties) 정보가 비어있습니다")

    return True
