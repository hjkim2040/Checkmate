from db.mongo import MongoDBManager
from db.mysql import MySQLManager
from utils.logging import setup_logger

logger = setup_logger(__name__)

async def check_existing_data(contract_id: int, mongo: MongoDBManager) -> dict:
    """기존 데이터 확인"""
    result = {
        'summary': False,
        'analysis': False
    }

    # 분석 및 요약 확인
    try:
        report = await mongo.find_report_by_contract_id(contract_id)
        if report:
            result['analysis'] = True
            result['summary'] = await mongo.has_summary_report(report["_id"])
    except Exception as e:
        logger.error(f"분석/요약 확인 오류: {e}")

    return result

# 정리 로직 함수 추가
async def cleanup_incomplete_data(contract_id, mongo: MongoDBManager, mysql: MySQLManager):
    try:
        # 1. MongoDB에서 ai_analysis_report 찾기
        report = await mongo.find_report_by_contract_id(contract_id)
        if report:
            report_id = report["_id"]

            # 2. 관련 서브 문서들 삭제
            for key in ("improvement_report", "missing_clause_report",
                        "risk_clause_report", "summary_report"):
                await mongo.delete_reports_by_analysis_id(report_id, key)

            # 3. 메인 리포트 삭제
            await mongo.delete_ai_analysis_report(report_id)

        await mysql.delete_contract_data(contract_id)

        logger.info(f"계약서 ID {contract_id}의 불완전한 분석 데이터 정리 완료")
    except Exception as cleanup_error:
        logger.error(f"데이터 정리 중 오류 발생: {cleanup_error}", exc_info=True)