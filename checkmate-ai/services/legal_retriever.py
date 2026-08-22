import asyncio
import json
import re
from typing import List, Tuple, Dict

from langchain.chains import LLMChain
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from nlp.llm import init_llm_model
from nlp.prompts import required_sections_prompt
from utils.logging import setup_logger

logger = setup_logger(__name__)


# 빈 응답 예외 클래스
class EmptyLegalInfoError(Exception):
    pass


# 계약 유형별 필수 조항 및 관련 법률 정보 가져오기
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(EmptyLegalInfoError),
    reraise=True
)
async def get_sections_from_gpt(llm, contract_type: str, existing_sections_text: str, category_name: str) -> list:
    """GPT를 통해 필수 조항 가져오기 (재시도 로직 포함)"""

    # LCEL 방식으로 프롬프트 체인 실행
    chain = required_sections_prompt | llm
    result = await chain.ainvoke({
        "contract_type": contract_type,
        "existing_sections": existing_sections_text,
        "category_name": category_name,
    })

    # 결과 텍스트 추출
    if hasattr(result, 'content'):
        result_text = result.content
    else:
        result_text = str(result)

    # 빈 응답 체크
    if not result_text or not result_text.strip():
        logger.error("빈 응답을 받았습니다")
        raise EmptyLegalInfoError("Empty response from GPT")

    # JSON 파싱
    json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    json_match = re.search(json_pattern, result_text)

    try:
        if json_match:
            gpt_required_sections = json.loads(json_match.group(1))
        else:
            gpt_required_sections = json.loads(result_text.strip())
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 실패: {e}")
        raise EmptyLegalInfoError(f"Invalid JSON response: {e}")

    # 응답 검증
    if not isinstance(gpt_required_sections, list):
        raise EmptyLegalInfoError("응답이 리스트 형식이 아닙니다")

    if not gpt_required_sections:
        raise EmptyLegalInfoError("빈 필수 조항 리스트를 받았습니다")

    # 각 항목 검증
    valid_sections = []
    for section in gpt_required_sections:
        if isinstance(section, dict) and "name" in section and section["name"]:
            valid_sections.append(section)

    if not valid_sections:
        raise EmptyLegalInfoError("유효한 필수 조항이 없습니다")

    return valid_sections


async def get_contract_type_requirements(contract_type: str, category_name:str, llm=None) -> List[str]:
    """계약 유형에 따른 필수 조항 목록 및 관련 법률 정보 가져오기"""

    # 계약 유형별 필수 조항 (정적 매핑)
    required_sections_map = {
        "employment_contract": [
            "근로계약기간",
            "근무장소",
            "종사업무",
            "근로시간",
            "임금",
            "휴일",
            "연차유급휴가",
            "퇴직급여",
            "취업규칙",
            "사회보험"
        ],
        "service_contract": [
            "용역의 내용",
            "용역기간",
            "용역대금",
            "성과물",
            "검수",
            "하자보수",
            "지적재산권",
            "비밀유지",
            "계약해지",
            "손해배상"
        ],
        "lease_contract": [
            "임대물건",
            "계약기간",
            "차임(임대료)",
            "보증금",
            "관리비",
            "수선의무",
            "계약갱신",
            "계약해지",
            "원상복구",
            "특약사항"
        ],
        "purchase_contract": [
            "매매목적물",
            "매매대금",
            "소유권이전",
            "인도",
            "하자담보책임",
            "계약해제",
            "손해배상",
            "특약사항",
            "비용부담",
            "위험부담"
        ],
        "agreement_contract": [
            "합의의 경위",
            "합의 내용",
            "상호 양보",
            "권리의무의 변동",
            "이행방법",
            "포기 조항",
            "비밀유지",
            "위반시 제재",
            "최종합의",
            "분쟁해결"
        ],
        "notification_contract": [
            "발신인 정보",
            "수신인 정보",
            "통지 일자",
            "통지 제목",
            "사실관계",
            "법적 근거",
            "요구사항",
            "기한",
            "불이행시 조치",
            "증거자료"
        ],
        "rules_contract": [
            "제정목적",
            "적용범위",
            "용어정의",
            "권한과 책임",
            "절차 및 방법",
            "제재조치",
            "시행일자",
            "개정절차",
            "부칙",
            "경과규정"
        ],
        "consent_contract": [
            "동의자 정보",
            "동의 대상",
            "동의 내용",
            "동의의 효력",
            "동의 철회",
            "정보보호",
            "책임제한",
            "동의일자",
            "유효기간",
            "서명"
        ],
        "terms_contract": [
            "약관의 목적",
            "용어정의",
            "이용계약",
            "서비스 내용",
            "이용요금",
            "이용자 의무",
            "제공자 의무",
            "면책조항",
            "분쟁해결",
            "약관변경"
        ],
        "damage_compensation_contract": [
            "손해배상의 원인",
            "손해배상의 범위",
            "손해배상 금액",
            "지급방법",
            "지연손해금",
            "면책사항",
            "소멸시효",
            "합의의 효력",
            "분쟁해결",
            "증거자료"
        ],
        "payment_order": [
            "채권자 정보",
            "채무자 정보",
            "채권의 원인",
            "청구금액",
            "지급기한",
            "지급계좌",
            "지연이자율",
            "강제집행",
            "이의신청",
            "송달방법"
        ],
        "other_contract": [
            "계약의 목적",
            "당사자의 권리와 의무",
            "계약기간",
            "대가",
            "이행시기",
            "계약의 변경",
            "해지/해제",
            "손해배상",
            "분쟁해결",
            "준거법"
        ]
    }

    # 기본 필수 조항
    required_sections = required_sections_map.get(contract_type, required_sections_map["other_contract"])

    # OpenAI를 통한 필수 조항 가져오기
    try:
        if llm is None:
            llm = init_llm_model(temperature=0.0)

        # 기존 필수 조항들을 문자열로 변환
        existing_sections_text = "\n".join([f"- {section}" for section in required_sections])

        # 재시도 로직이 포함된 함수 호출
        gpt_required_sections = await get_sections_from_gpt(llm, contract_type, existing_sections_text, category_name)
        # 필수 조항 이름만 추출
        gpt_section_names = [section["name"] for section in gpt_required_sections]

        # GPT가 제안한 조항과 정적 매핑 조항 병합
        required_sections = required_sections + gpt_section_names

    except EmptyLegalInfoError as e:
        logger.error(f"필수 조항 추출 오류 (빈 응답): {e}")
        logger.info("기본 필수 조항만 사용합니다")
    except Exception as e:
        logger.error(f"GPT 필수 조항 추출 오류: {e}")

    return required_sections


async def get_clause_specific_laws_parallel(structured_contract, vector_store) -> Dict[str, Dict]:
    """모든 조항에 대한 법률 검색 (배치 임베딩 처리로 최적화)"""

    contract_type = structured_contract.metadata.contract_type

    # 1. 모든 쿼리를 먼저 수집
    queries = []
    sections = []

    for section in structured_contract.sections:
        query = f"{contract_type} {section.title} 법적 요건"
        queries.append(query)
        sections.append(section)

    logger.info(f"총 {len(queries)}개 조항에 대한 임베딩 생성 시작")

    # 2. 배치로 임베딩 생성 (한 번의 API 호출로 모든 임베딩 생성)
    try:
        # embed_documents를 사용하여 배치 처리
        embeddings = vector_store.embeddings.embed_documents(queries)
        logger.info(f"임베딩 생성 완료: {len(embeddings)}개")
    except Exception as e:
        logger.error(f"배치 임베딩 생성 오류: {e}")
        # 오류 발생 시 개별 처리로 폴백
        raise
    # 3. 각 임베딩으로 검색 (병렬 처리)
    search_tasks = []

    for section, embedding in zip(sections, embeddings):
        task = search_by_vector_async(vector_store, embedding, section)
        search_tasks.append((section.number, task))

    # 4. 병렬 검색 실행 (배치로 처리)
    results = {}
    batch_size = 10

    for i in range(0, len(search_tasks), batch_size):
        batch = search_tasks[i:i + batch_size]
        batch_results = await asyncio.gather(*[task for _, task in batch])

        # 결과 매핑
        for (clause_num, _), result in zip(batch, batch_results):
            results[clause_num] = result

    logger.info(f"법률 검색 완료: {len(results)}개 조항")
    return results


async def search_by_vector_async(vector_store, embedding: List[float], section) -> Dict:
    """벡터로 직접 검색"""
    try:
        # similarity_search_by_vector 사용 (임베딩 변환 과정 없음)
        search_results = await asyncio.to_thread(
            vector_store.similarity_search_by_vector,
            embedding=embedding,
            k=3
        )

        return {
            "title": section.title,
            "content": section.content[:200],
            "laws": search_results
        }
    except Exception as e:
        logger.error(f"벡터 검색 오류: {e}")
        return {
            "title": section.title,
            "content": section.content[:200],
            "laws": []
        }
