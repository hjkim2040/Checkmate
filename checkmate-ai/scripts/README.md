# 법령 데이터 적재 스크립트

RAG 검색에 사용하는 법령 조문을 Qdrant에 적재하는 **1회성 배치 스크립트**입니다.
서비스 코드(`db/qdrant.py`, `nlp/embeddings.py`)와 분리되어 있으며, 적재 당시 사용한 코드를 그대로 보관합니다.

## 파이프라인

```
국가법령정보센터 DOCX (법령 18건)
  → docx_to_json.py        조문 단위 분리 (제N조 / 제N조의M 기준)
  → legal_document_loader.py   JSON 로드 · 필수 필드 검증
  → ingest_qdrant.py       1,000자 단위 청킹(overlap 200) → 임베딩 → Qdrant 저장
```

| 파일 | 역할 |
|---|---|
| `docx_to_json.py` | DOCX를 조문 단위 JSON으로 변환. 상위 폴더명을 `law_name`으로 사용 |
| `legal_document_loader.py` | JSON 로드, 필드 검증, 적재 실행 진입점 |
| `ingest_qdrant.py` | 컬렉션 생성(코사인, `law_name`·`type` 인덱스), 청킹, 저장 |
| `ingest_embeddings.py` | SentenceTransformer 로컬 임베딩 |

## 데이터 형식

입력 폴더 구조 (폴더 하나 = 법령 1건, 법률·시행령 DOCX 포함):
```
laws/
├── 근로기준법/
│   ├── 근로기준법(법률).docx
│   └── 근로기준법 시행령.docx
└── ...
```

변환 결과 예시:
```json
{
  "content": "제1조(목적) 이 법은 헌법에 따라 근로조건의 기준을 정함으로써 ...",
  "title": "목적",
  "type": "법률조문",
  "law_name": "근로기준법",
  "article_number": "제1조"
}
```

Qdrant payload는 `{"page_content", "metadata"}` 형식으로 저장되며, 서비스의 `QdrantDB._to_document`가 이 형식을 읽습니다.

## 실행 방법

법령 원본(DOCX)과 변환된 JSON은 레포에 포함하지 않습니다.
[국가법령정보센터](https://www.law.go.kr)에서 법령별 DOCX를 내려받아 위 구조로 배치합니다.
`scripts/sample/근로기준법.json`은 형식 확인용 샘플입니다. (최신 개정본 기준이라 적재 당시 버전과 다를 수 있음)

`checkmate-ai/` 디렉터리에서 실행합니다.

```bash
# 1. DOCX → JSON (<laws_dir>: 법령별 폴더가 있는 경로)
python scripts/docx_to_json.py <laws_dir> --batch --out-dir <json_dir>

# 2. 형식 검증만
python -m scripts.legal_document_loader --folder scripts/sample --validate-only

# 3. 적재
python -m scripts.legal_document_loader --folder <json_dir>
```

필요 환경변수: `QDRANT_URL`, `QDRANT_API_KEY`, `EMBEDDING_REPO_ID`
추가 의존성: `python-docx`, `sentence-transformers`, `langchain-qdrant`

## 적재 대상 법령
1. 개인정보보호법
2. 근로자퇴직급여 보장법
3. 금융소비자 보호법
4. 민법
5. 민사소송법
6. 민사집행법
7. 상가건물 임대차보호법
8. 상법
9. 소비자기본법
10. 약관의 규제에 관한 법률
11. 임금채권보장법
12. 전자문서 및 전자거래 기본법
13. 전자상거래법
14. 제품안전기본법
15. 주택임대차보호법
16. 최저임금법
17. 행정절차법
18. 근로기준법

## 참고
- 적재는 로컬 SentenceTransformer로, 서비스의 검색 쿼리 임베딩은 HF Inference API(`AsyncInferenceClient`)로 수행합니다.
  - 같은 EMBEDDING_REPO_ID 사용