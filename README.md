## 👤 개인 기여 — 김성찬 (AI Server / Backend)

> 6인 팀 프로젝트입니다. 아래는 제가 담당한 부분이며, 원본 팀 README는 그 아래에 그대로 두었습니다.
> 
> 📄 포트폴리오: [링크](https://trusting-gooseberry-30e.notion.site/Checkmate-AI-3b7f2546fed4804cae7dca9d353d83e8?source=copy_link)

### 담당 범위
- **AI 계약서 분석 서버(FastAPI) 전담** : OCR 결과 구조화, 누락·위험·개선 분석, 요약, 확인 질문 생성
- **RAG 법률 검색** : 법령 18종을 조문 단위로 Qdrant에 적재, 조항별 관련 법령을 분석 근거로 주입
- **서버 간 비동기 연동** : Spring Boot 이벤트 발행 → FastAPI 백그라운드 처리 → 웹훅 콜백

### 코드 위치
**AI 서버 (전담)** : [`checkmate-ai/`](https://github.com/hjkim2040/Checkmate/tree/85b951fb1c3112b31189bdc292c21a529531c8fe/checkmate-ai)

| 구분 | 경로                                                                                                                                                                                                                                                                                            |
|---|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 분석 파이프라인 (3라운드 병렬 실행) | [`/pipeline.py`](https://github.com/hjkim2040/Checkmate/blob/85b951fb1c3112b31189bdc292c21a529531c8fe/checkmate-ai/services/pipeline.py)                                                                                                                                                      |
| 프롬프트 4종 | [`/prompts.py`](https://github.com/hjkim2040/Checkmate/blob/bfbfab6ef036b417612755150379bf12c5a52fd7/checkmate-ai/nlp/prompts.py)                                                                                                                                                             |
| RAG 법령 검색 · 비동기 임베딩 | [`/embeddings.py`](https://github.com/hjkim2040/Checkmate/blob/bfbfab6ef036b417612755150379bf12c5a52fd7/checkmate-ai/nlp/embeddings.py), [`/legal_retriever.py`](https://github.com/hjkim2040/Checkmate/blob/bfbfab6ef036b417612755150379bf12c5a52fd7/checkmate-ai/services/legal_retriever.py) |
| 웹훅 콜백 | [`/webhook.py`](https://github.com/hjkim2040/Checkmate/blob/bfbfab6ef036b417612755150379bf12c5a52fd7/checkmate-ai/services/webhook.py)                                                                                                                                                        |

**Spring 연동 (담당 부분만)** 

| 구분 | 경로                                                                                                                                                                                                                     |
|-|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| AFTER_COMMIT 이벤트 리스너 | [`/AiAnalysisListener.java`](https://github.com/hjkim2040/Checkmate/blob/bfbfab6ef036b417612755150379bf12c5a52fd7/checkmate-be/src/main/java/com/checkmate/domain/aianalysisreport/service/AiAnalysisListener.java)    |
| 이벤트 발행 지점 | [계약서 업로드](https://github.com/hjkim2040/Checkmate/blob/c2044792e98c9c45fd60687eabe619ce44da6148/checkmate-be/src/main/java/com/checkmate/domain/contract/service/ContractService.java#L82-L85), [생성 계약서 저장](https://github.com/hjkim2040/Checkmate/blob/c2044792e98c9c45fd60687eabe619ce44da6148/checkmate-be/src/main/java/com/checkmate/domain/contract/service/ContractGeneratedFileService.java#L124-L130) |
| FastAPI 호출 (WebClient) | [`/WebClientConfig.java`](https://github.com/hjkim2040/Checkmate/blob/bfbfab6ef036b417612755150379bf12c5a52fd7/checkmate-be/src/main/java/com/checkmate/global/config/WebClientConfig.java#L43-L98)                    |
| 웹훅 수신 | [`/webhook`](https://github.com/hjkim2040/Checkmate/tree/bfbfab6ef036b417612755150379bf12c5a52fd7/checkmate-be/src/main/java/com/checkmate/domain/webhook)                                                             |

### 주요 개선
| 문제 | 해결 | 결과 | 코드       |
|---|---|---|----------|
| 단일 프롬프트로 응답 지연·품질 저하 | 목적별 4개 분리 + asyncio.gather 병렬 실행 | 응답 2분 이상 → 1분 내외 | [코드](링크) |
| LLM의 근거 없는 판단 | 법령 18종 조문 단위 RAG 구축 | 분석이 실제 조문을 참고 | [코드](링크) |
| 조항별 직렬 임베딩·검색 | 비동기 임베딩 + Qdrant 배치 검색 | 벡터 검색 요청 N회 → 1회 | [코드](링크) |
| 1분 이상 걸리는 분석으로 타임아웃 위험 | AFTER_COMMIT 이벤트 + BackgroundTasks + 웹훅 | AI 서버 장애와 업로드 기능 분리 | [코드](링크) |

### 처리 흐름
```mermaid
sequenceDiagram
    participant C as Client
    participant S as Spring Boot
    participant A as FastAPI (AI)
    C->>S: 계약서 업로드
    S-->>C: 즉시 응답
    S->>A: 커밋 후(AFTER_COMMIT) 분석 요청
    A-->>S: 즉시 응답
    A->>A: BackgroundTasks로 분석 파이프라인 실행
    A->>S: 웹훅 콜백 (성공/실패, X-API-Key)
    S->>C: WebSocket 완료 알림
```

---

# 목차

1. [프로젝트 소개](#프로젝트-소개)
2. [주요 화면 및 기능 소개](#주요-화면-및-기능-소개)
3. [개발 환경](#개발-환경)
4. [팀원 소개](#팀원-소개)

<br/>

# 🥸 프로젝트 소개

#### 1. 개요

- 서비스 명 : CHECKMATE(체크메이트)
- 한 줄 소개 : AI 기반 계약서 분석 서비스
- 기간 : 2025.04.14 ~ 2025.05.22 (39일)

#### 2. 기획 배경

- 목적 : 계약서에 대한 지식이 많지 않은 사회 초년생들이 불공정한 계약을 하지 않도록 돕기 위한 서비스

<br/>

# 🎯 주요 화면 및 기능 소개

#### 메인화면
![image](docs/asset/메인페이지.gif)
![image](docs/asset/모바일%20관련%20뉴스.gif)
- 체크메이트 서비스를 설명하는 내용으로 구성
- 페이지의 최하단에는 네이버 뉴스 API를 이용하여 계약 관련된 뉴스를 제공
- 네이버 뉴스를 Redis에 캐싱하여 API 호출↓

#### 계약서 분석
![image](docs/asset/분석%20업로드.gif)
![image](docs/asset/모바일%20분석%20파일%20업로드.gif)
- 계약서 유형을 선택하면 업로드 할 수 있는 페이지로 전환
- 업로드 페이지에서 HWP, PDF, JPG, PNG 확장자의 계약서를 업로드 할 수 있고, 업로드 되면 ClamAV를 통해 바이러스 검사 진행
- 안전한 파일인게 확인되면 AES-GCM 암호화 하여 DEK를 이용해 2-of-2 방식으로 각기 다른 데이터베이스에 분산 저장

![image](docs/asset/분석페이지.gif)
![image](docs/asset/모바일%20분석결과%20대시보드.gif)
- 분석이 완료되면 WebSocket+Stomp를 이용하여 실시간 알림을 제공
- 분석 결과는 LangChain에 OpenAI API를 이용하여 비동기 병렬형태로 진행
- 분석 프롬프트는 RAG를 이용하여 사전 저장된 Qdrant 법률 데이터를 이용하여 벡터 조회를 통해 나온 결과를 프롬프트에 증강하여 신뢰성과 안정성 증가

#### 계약서 작성 가이드
![image](docs/asset/작성%20가이드.gif)
- 계약서를 작성할 때, 어떤 순서로 작성을 하면 되는지에 대한 가이드 페이지

#### 계약서 작성 전 주의사항
![image](docs/asset/작성%20전%20주의사항.gif)
![image](docs/asset/모바일%20작성%20전%20주의사항.gif)
- 계약서 작성 전 주의사항을 모달창으로 제공

#### 계약서 작성
![image](docs/asset/계약서%20작성.gif)
![image](docs/asset/모바일%20질문리스트.gif)
![image](docs/asset/모바일%20계약서%20작성.gif)
- 카테고리 별 계약서 템플릿을 제공하여 사용자가 필드에 값을 채우면 계약서를 제공
- 자동저장 기능을 통해 이전에 작성한 내용도 쉽게 확인

#### 마이페이지
![image](docs/asset/마이페이지.gif)
![image](docs/asset/내계약서%20-%20분석페이지.gif)
![image](docs/asset/법원.gif)
![image](docs/asset/모바일%20주변%20법원.gif)
- 마이페이지의 대시보드에는 계약 활동, 알림, 최근 활동 내역을 제공
- 내 계약서 탭으로 이동하면 사용자가 진행했던 계약서 관련 상태를 확인
- d3.js를 통해 지도를 시각화하여 렌더링하는 시간을 감소

#### 계약서 저장
![image](docs/asset/최종%20계약서.gif)
![image](docs/asset/모바일%20최종%20계약서.gif)
- 저장하기 버튼을 누르면 pdf형태로 사용자에게 제공

#### 전자서명
- DropSignAPI를 이용하여 전자서명 구현


<br/>

# 👻 개발 환경

### <code>[ 기술 스택 ]</code>

### Frontend
<img src="https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=React&logoColor=white"/>
<img src="https://img.shields.io/badge/Typescript-3178C6?style=for-the-badge&logo=Typescript&logoColor=white"/>
<img src="https://img.shields.io/badge/Tailwind%20CSS-06B6D4?style=for-the-badge&logo=Tailwind%20CSS&logoColor=white"/> <br />

### Backend
<img src="https://img.shields.io/badge/SpringBoot-6DB33F?style=for-the-badge&logo=springboot&logoColor=white"/>
<img src="https://img.shields.io/badge/Spring%20Security-6DB33F?style=for-the-badge&logo=springsecurity&logoColor=white"/>
<img src="https://img.shields.io/badge/JWT-000000?style=for-the-badge&logo=jsonwebtokens&logoColor=white"/>
<img src="https://img.shields.io/badge/ClamAV-0079C1?style=for-the-badge"/>
<img src="https://img.shields.io/badge/AES--GCM-000000?style=for-the-badge&logo=lock&logoColor=white"/> <br />

### AI
<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
<img src="https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=LangChain&logoColor=white"/>
<img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white"/> <br />

### Database
<img src="https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white"/>
<img src="https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white"/>
<img src="https://img.shields.io/badge/Redis-FF4438?style=for-the-badge&logo=redis&logoColor=white"/>
<img src="https://img.shields.io/badge/Qdrant-000000?style=for-the-badge"/> <br />

### Infra/DevOps
<img src="https://img.shields.io/badge/EC2-FF9900?style=for-the-badge&logo=amazonec2&logoColor=white"/>
<img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white"/>
<img src="https://img.shields.io/badge/AWS%20S3-569A31?style=for-the-badge&logo=Amazon%20S3&logoColor=white"/>
<img src="https://img.shields.io/badge/CloudFront-232F3E?style=for-the-badge&logo=Amazon%20CloudFront&logoColor=white"/>
<img src="https://img.shields.io/badge/GitLab%20Runner-FC6D26?style=for-the-badge&logo=gitlab&logoColor=white"/> <br />

### 협업 툴
<img src="https://img.shields.io/badge/Mattermost-0058CC?style=for-the-badge&logo=mattermost&logoColor=white"/>
<img src="https://img.shields.io/badge/GitLab-FC6D26?style=for-the-badge&logo=gitlab&logoColor=white"/> <br />

<br/>

### <code>[ ERD ]</code>
![image](docs/asset/ERD.jpg)

### <code>[ 아키텍처 ]</code>
![image](docs/asset/아키텍처.jpg)

### <code>[ 화면 설계서 ]</code>
![image](docs/asset/화면%20설계서.png)


<br/>

# 🥳 팀원 소개
| 이영재(팀장) | 손서현 | 신승아 | 송창현 | 김성찬 | 고태연 |
| --- | --- | --- | --- | --- | --- |
| BE | BE | FE | FE | BE | FE |
<br/>
