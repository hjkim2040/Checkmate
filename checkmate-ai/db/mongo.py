from datetime import datetime

import motor.motor_asyncio
from bson import ObjectId

from utils.logging import setup_logger

logger = setup_logger(__name__)

from config.settings import (
    MONGO_URI, MONGO_DB, AI_ANALYSIS_REPORT_COLLECTION,
    IMPROVEMENT_REPORT_COLLECTION, MISSING_CLAUSE_REPORT_COLLECTION,
    RISK_CLAUSE_REPORT_COLLECTION
)
from models.enums import Importance, RiskLevel


class MongoDBManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.collections = {}

    async def connect(self):
        """MongoDB 연결 및 설정"""

        try:
            # MongoClient 옵션 설정
            self.client = motor.motor_asyncio.AsyncIOMotorClient(
                MONGO_URI,
                serverSelectionTimeoutMS=5000
            )

            self.db = self.client[MONGO_DB]

            # 각 컬렉션 가져오기
            self.collections = {
                "ai_analysis_report": self.db[AI_ANALYSIS_REPORT_COLLECTION],
                "improvement_report": self.db[IMPROVEMENT_REPORT_COLLECTION],
                "missing_clause_report": self.db[MISSING_CLAUSE_REPORT_COLLECTION],
                "risk_clause_report": self.db[RISK_CLAUSE_REPORT_COLLECTION],
                "summary_report": self.db["summary_report"],
                "keyShare": self.db["keyShare"],
            }

        except Exception as e:
            logger.error(f"MongoDB 설정 오류: {e}")
            raise

    async def disconnect(self):
        """MongoDB 연결 종료"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

    async def get_share_b(self, file_id: int):
        """암호화 키 조회"""
        doc = await self.collections.get("keyShare").find_one({"fileId": file_id})
        return doc and doc.get("shareB")

    async def save_ai_analysis_report(self, contract_id: int) -> ObjectId:
        """AI 분석 보고서 저장"""
        # AI 분석 보고서 생성 (Spring Boot 엔티티와 일치)
        ai_analysis_report = {
            "contractId": contract_id,
            "createdAt": datetime.now()
        }

        # MongoDB에 저장
        result = await self.collections.get("ai_analysis_report").insert_one(ai_analysis_report)

        # 생성된 ObjectId 가져오기
        ai_analysis_report_id = result.inserted_id

        logger.info(f"AI 분석 보고서 저장 완료: {ai_analysis_report_id}")
        return ai_analysis_report_id

    async def save_summary_report(self, ai_analysis_report_id: ObjectId, description: str) -> ObjectId:
        """요약 보고서 저장"""
        doc = {
            "aiAnalysisReportId": ai_analysis_report_id,
            "description": description,
            "createdAt": datetime.now()
        }
        result = await self.collections.get("summary_report").insert_one(doc)
        return result.inserted_id

    async def save_improvement_report(self, ai_analysis_report_id: ObjectId, description: str):
        """개선 사항 보고서 저장"""
        # 개선 사항 보고서 생성 (Spring Boot 엔티티와 일치)
        improvement_report = {
            "aiAnalysisReportId": ai_analysis_report_id,
            "description": description,
            "createdAt": datetime.now()
        }

        # MongoDB에 저장
        result = await self.collections.get("improvement_report").insert_one(improvement_report)
        return result.inserted_id

    async def save_missing_clause_report(self, ai_analysis_report_id: ObjectId, severity: str, description: str):
        """누락 조항 보고서 저장"""
        # 중요도 변환 (Spring Boot Enum과 일치)
        importance = Importance.MEDIUM
        if severity.lower() == "높음":
            importance = Importance.HIGH
        elif severity.lower() == "낮음":
            importance = Importance.LOW

        # 누락 조항 보고서 생성 (Spring Boot 엔티티와 일치)
        missing_clause_report = {
            "aiAnalysisReportId": ai_analysis_report_id,
            "importance": importance.value,
            "description": description,
            "createdDate": datetime.now()  # Spring Boot 엔티티의 필드명과 일치
        }

        # MongoDB에 저장
        result = await self.collections.get("missing_clause_report").insert_one(missing_clause_report)
        return result.inserted_id

    async def save_risk_clause_report(self, ai_analysis_report_id: ObjectId, severity: str, original_text: str,
                                      description: str):
        """위험 조항 보고서 저장"""
        # 위험 수준 변환 (Spring Boot Enum과 일치)
        risk_level = RiskLevel.MEDIUM
        if severity.lower() == "높음":
            risk_level = RiskLevel.HIGH
        elif severity.lower() == "낮음":
            risk_level = RiskLevel.LOW

        # 위험 조항 보고서 생성 (Spring Boot 엔티티와 일치)
        risk_clause_report = {
            "aiAnalysisReportId": ai_analysis_report_id,
            "riskLevel": risk_level.value,
            "originalText": original_text,
            "description": description,
            "createdAt": datetime.now()
        }

        # MongoDB에 저장
        result = await self.collections.get("risk_clause_report").insert_one(risk_clause_report)
        return result.inserted_id

    async def delete_reports_by_analysis_id(self, ai_analysis_report_id: ObjectId, collection_key: str) -> int:
        """특정 분석 리포트에 속한 하위 리포트 전체 삭제 (재분석 시 멱등성 확보용)"""
        result = await self.collections.get(collection_key).delete_many(
            {"aiAnalysisReportId": ai_analysis_report_id}
        )
        return result.deleted_count

# MongoDB 클라이언트 인스턴스 생성
mongo_manager = MongoDBManager()
