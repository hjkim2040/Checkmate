from langchain.prompts import PromptTemplate
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate

# 계약서 구조화 프롬프트
# ChatPromptTemplate을 사용하는 방식 (권장)
contract_structuring_chat_prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content="당신은 계약서 분석 전문가입니다. 계약서 텍스트를 분석하여 구조화된 정보로 변환해주세요."),
    HumanMessagePromptTemplate.from_template("""
다음 계약서 텍스트를 분석하여 구조화된 정보로 변환해주세요. 
JSON 형식으로 아래 내용을 포함해야 합니다:

1. 계약서 제목 (title)
2. 계약 날짜 (date)
3. 계약 당사자 정보 (parties) - 각 당사자의 역할과 이름
4. 계약서 유형 (contract_type)
5. 조항 목록 (sections) - 각 조항의 번호(제 ~조), 제목, 내용, 유형

계약서 유형 코드는 다음 중 하나를 사용하세요:
- employment_contract (임직원계약, 근로계약)
- service_contract (용역계약)
- lease_contract (임대차계약)
- purchase_contract (매매계약)
- agreement_contract (합의서, 협의서)
- notification_contract (통지서, 확인서, 신청서)
- rules_contract (규칙, 방침)
- consent_contract (동의서, 승낙서, 보고서)
- terms_contract (약관)
- damage_compensation_contract (손해배상, 계약이행)
- payment_order (지급명령)
- other_contract (기타)

계약서 카테고리 이름:
```
{category_name}
```

계약서 내용:
```
{contract_text}
```

다음 JSON 형식으로만 응답해주세요:
```json
{{
  "title": "계약서 제목",
  "date": "계약 날짜",
  "parties": [
    {{"role": "역할1(예: 갑/매도인/임대인)", "name": "이름1"}},
    {{"role": "역할2(예: 을/매수인/임차인)", "name": "이름2"}}
  ],
  "contract_type": "계약서 유형 코드",
  "sections": [
    {{
      "number": "조항 번호(제 ~조)",
      "title": "조항 제목",
      "content": "조항 전체 내용",
      "type": "조항 유형(예: standard(표준), special(특약))"
    }}
  ]
}}
```

JSON 구조만 응답하고 다른 설명은 포함하지 마세요.
""")
])

# 계약서 분석 프롬프트
# ChatPromptTemplate을 사용하는 방식 (권장)
missing_sections_prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content="""당신은 계약서 분석 전문가입니다. 
    계약서에서 누락된 필수 조항을 찾는 것이 당신의 전문 분야입니다.
    중요: 응답은 반드시 유효한 JSON 형식이어야 합니다. 추가 설명이나 주석을 포함하지 마세요."""),
    HumanMessagePromptTemplate.from_template("""
다음 계약서를 분석하여 누락된 필수 조항을 찾아주세요:

계약서 제목: {title}
계약서 유형: {contract_type}
계약서 카테고리 이름: {category_name}

계약서 전체 내용:
{content}

이 유형의 계약서에 포함되어야 할 필수 조항들:
{required_sections}

조항 관련 법률 정보:
아래 법률은 검색으로 찾은 후보이며, 조항과 관련이 없으면 무시하라. 인용할 때는 법률명과 조문을 밝혀라.
{legal_context}

다음 사항들을 분석해주세요:

**누락된 필수 조항 확인**: 
   - 위에 나열된 필수 조항들이 계약서에 포함되어 있는지 확인하고, 누락된 조항을 찾아주세요.
   - 조항의 제목이 정확히 일치하지 않더라도 내용상 존재한다면 포함된 것으로 판단
   - 누락된 경우 그 중요도를 평가 (높음/중간/낮음)

아래 JSON 형식으로만 응답해주세요. 다른 텍스트는 절대 포함하지 마세요:
```
{{
  "missing_sections": [
    {{
      "description": "누락된 필수 조항에 대한 상세한 설명",
      "severity": "높음/중간/낮음"
    }}
  ]
}}
```

주의사항:
- JSON 내의 모든 문자열에서 줄바꿈은 \\n으로 이스케이프하세요
- 따옴표는 \\"로 이스케이프하세요
- 배열의 마지막 요소 뒤에 쉼표를 넣지 마세요
- 객체의 마지막 속성 뒤에 쉼표를 넣지 마세요
""")
])

improvements_prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content="""당신은 계약서 분석 전문가입니다. 
    계약서의 개선점과 보완사항을 찾는 것이 당신의 전문 분야입니다.
    중요: 응답은 반드시 유효한 JSON 형식이어야 합니다. 추가 설명이나 주석을 포함하지 마세요."""),
    HumanMessagePromptTemplate.from_template("""
다음 계약서를 검토하여 개선사항을 제안해주세요:

계약서 제목: {title}
계약서 유형: {contract_type}
계약서 카테고리 이름: {category_name}

계약서 전체 내용:
{content}

조항 관련 법률 정보:
아래 법률은 검색으로 찾은 후보이며, 조항과 관련이 없으면 무시하라. 인용할 때는 법률명과 조문을 밝혀라.
{legal_context}

**개선 권장사항**:
- 계약서 전체 관점에서 개선이 필요한 부분 찾기
- 조항의 명확성, 구체성, 법적 완성도 평가
- 모호한 표현이나 해석의 여지가 있는 부분 지적
- 보완이 필요한 세부사항 제안
- 각 개선사항에 대해 구체적인 수정 방향 제시

아래 JSON 형식으로만 응답해주세요. 다른 텍스트는 절대 포함하지 마세요:
```
{{
  "improvement_recommendations": [
    {{
      "description": "개선이 필요한 부분에 대한 구체적인 설명"
    }}
  ]
}}
```

주의사항:
- JSON 내의 모든 문자열에서 줄바꿈은 \\n으로 이스케이프하세요
- 따옴표는 \\"로 이스케이프하세요
- 배열의 마지막 요소 뒤에 쉼표를 넣지 마세요
- 객체의 마지막 속성 뒤에 쉼표를 넣지 마세요
""")
])

risk_analysis_prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content="""당신은 계약서 분석 전문가입니다. 
    계약 당사자에게 불리하거나 위험한 조항을 찾는 것이 당신의 전문 분야입니다.
    중요: 응답은 반드시 유효한 JSON 형식이어야 합니다. 추가 설명이나 주석을 포함하지 마세요."""),
    HumanMessagePromptTemplate.from_template("""
다음 계약서에서 위험한 조항을 찾아주세요:

계약서 제목: {title}
계약서 유형: {contract_type}
계약서 카테고리 이름: {category_name}

계약서 전체 내용:
{content}

조항 관련 법률 정보:
아래 법률은 검색으로 찾은 후보이며, 조항과 관련이 없으면 무시하라. 인용할 때는 법률명과 조문을 밝혀라.
{legal_context}

**위험한 조항 분석**:
- 계약 당사자에게 불리하거나 위험할 수 있는 조항 찾기
- 일방적으로 불공정한 조건 확인
- 과도한 책임이나 의무를 부과하는 조항 식별
- 권리 행사를 제한하는 조항 검토
- 분쟁 발생 시 불리할 수 있는 조항 분석
- 각 위험 조항에 대해 구체적인 위험성 설명

아래 JSON 형식으로만 응답해주세요. 다른 텍스트는 절대 포함하지 마세요:
```
{{
  "risk_clauses": [
    {{
      "description": "위험 요소에 대한 상세한 설명",
      "severity": "높음/중간/낮음",
      "original_text": "위험한 조항의 원문 전체 (조항 번호와 제목 포함)",
    }}
  ]
}}
```

주의사항:
- JSON 내의 모든 문자열에서 줄바꿈은 \\n으로 이스케이프하세요
- 따옴표는 \\"로 이스케이프하세요
- 배열의 마지막 요소 뒤에 쉼표를 넣지 마세요
- 객체의 마지막 속성 뒤에 쉼표를 넣지 마세요
""")
])

questions_generation_prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content="""당신은 계약서 분석 전문가입니다. 
    계약 체결 전 확인해야 할 중요한 질문들을 생성하는 것이 당신의 전문 분야입니다.
    중요: 응답은 반드시 유효한 JSON 형식이어야 합니다. 추가 설명이나 주석을 포함하지 마세요."""),
    HumanMessagePromptTemplate.from_template("""
다음 계약서를 검토하고 중요한 질문들을 생성해주세요:

계약서 제목: {title}
계약서 유형: {contract_type}
계약서 카테고리 이름: {category_name}

계약서 전체 내용:
{content}

**중요 질문 생성**:
- 계약 상대방이나 변호사와 미팅 시 물어볼 최소 5개, 최대 10개의 중요한 질문 생성
- 계약 조건의 명확화를 위한 질문
- 숨겨진 위험이나 불명확한 부분에 대한 질문
- 실무적 이행 방법에 대한 질문
- 분쟁 발생 시 해결 방법에 대한 질문
- 각 질문은 구체적이고 실무적이어야 함

아래 JSON 형식으로만 응답해주세요. 다른 텍스트는 절대 포함하지 마세요:
```
{{
  "questions": [
    "질문 내용 1",
    "질문 내용 2",
    "질문 내용 3",
    "질문 내용 4",
    "질문 내용 5"
  ]
}}
```

주의사항:
- JSON 내의 모든 문자열에서 줄바꿈은 \\n으로 이스케이프하세요
- 따옴표는 \\"로 이스케이프하세요
- 배열의 마지막 요소 뒤에 쉼표를 넣지 마세요
- 객체의 마지막 속성 뒤에 쉼표를 넣지 마세요
""")
])

# 계약서 유형별 필수 조항 프롬프트
required_sections_prompt = PromptTemplate(
    template="""
    다음 유형의 계약서에 포함되어야 할 필수 조항과 그 중요도를 알려주세요.

    계약서 유형: {contract_type}
    계약서 카테고리 이름: {category_name}

    이미 존재하는 기본 필수 조항들:
    {existing_sections}

    위의 기본 필수 조항들과 중복되지 않는 추가 필수 조항들만 제안해주세요.
    
    유사한 내용이나 동의어는 제외하고, 정말 추가로 필요한 조항들만 알려주세요.

    아래 JSON 형식으로만 응답하고, 다른 텍스트는 포함하지 마세요:
    ```json
    [
      {{"name": "필수 조항명", "description": "간단한 설명"}},
      {{"name": "필수 조항명", "description": "간단한 설명"}}
    ]
    ```
    
    주의: JSON 배열의 마지막 요소 뒤에 쉼표를 넣지 마세요.
    """,
    input_variables=["contract_type", "existing_sections"]
)

SYSTEM_PROMPT = """
당신은 복잡한 법률·의료 문서를 일반인도 이해하기 쉬운 평이한 한국어로 요약하는 전문가입니다.
아래 문서를 요약할 때는 다음 다섯 가지 항목을 반드시 포함하세요:
1. 문서의 주된 목적 (예: 대출계약서, 의료동의서) – 3~4줄
2. 핵심 조건 및 조항 – 평이한 언어로
3. 중요한 기한·날짜
4. 각 당사자의 주요 책임·의무
5. 주의해야 할 위험 요소나 유의사항

– 가능한 한 짧고 명확한 불릿포인트로 정리
– 법률 용어가 불가피할 경우, 괄호 안에 간단히 풀이
– 출력은 한국어로만, 불필요한 해설 금지
"""

USER_PROMPT_TEMPLATE = """
Document text:

{all_text}

Simplified Summary in Korean:
"""
