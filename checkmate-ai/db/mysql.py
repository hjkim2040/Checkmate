from datetime import datetime

import asyncio
import pymysql
import aiomysql

from config.settings import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USERNAME,
    MYSQL_PASSWORD, MYSQL_DATABASE
)
from models.enums import ClauseType
from utils.logging import setup_logger

logger = setup_logger(__name__)


class MySQLManager:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """MySQL 연결"""
        try:
            self.pool = await aiomysql.create_pool(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USERNAME,
                password=MYSQL_PASSWORD,
                db=MYSQL_DATABASE,
                autocommit=True,
                connect_timeout=30,  # 연결 타임아웃 증가
                minsize=1,
                maxsize=10,
                pool_recycle=1800,
            )

            logger.info("MySQL Pool 생성 완료")

        except Exception as e:
            logger.error(f"MySQL 연결 오류: {e}")
            raise

    async def disconnect(self):
        """MySQL 연결 종료"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("MySQL Pool 종료 완료")

    async def get_contract_file_info(self, contract_id: int, file_category: str = "VIEWER"):
        """계약서 파일 정보 조회"""
        async def operation(pool, cid, fc):
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    query = """
                            SELECT id, file_address, encrypted_data_key, iv
                            FROM contract_file
                            WHERE contract_id = %s \
                              AND file_category = %s \
                            """
                    await cur.execute(query, (contract_id, file_category))
                    return await cur.fetchone()

        return await self.with_retry(operation, contract_id, file_category)

    async def save_contract_clauses(self, contract_id: int, sections: list):
        """계약서 조항들을 저장"""
        async def operation(pool, cid, secs):

            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    values = []
                    for section in sections:
                        # clause_type을 Enum으로 변환
                        clause_type = self._convert_to_clause_type(section.get('type', 'standard'))
                        values.append((
                            contract_id,
                            section.get('number', ''),
                            section.get('title', ''),
                            section.get('content', ''),
                            clause_type.value,
                            datetime.now()
                        ))
                    await cur.execute(
                        "DELETE FROM clause WHERE contract_id = %s", (contract_id,)
                    )
                    sql = """
                          INSERT INTO clause
                          (contract_id, clause_number, clause_title, clause_content, clause_type, created_at)
                          VALUES (%s, %s, %s, %s, %s, %s) \
                          """
                    await cur.executemany(sql, values)
                    logger.info(f"계약서 {contract_id}의 조항 저장 완료")
                    return True

        return await self.with_retry(operation, contract_id, sections)

    async def save_questions_batch(self, contract_id: int, contract_category_id: int, questions: list):
        """질문 목록을 일괄 저장"""
        if not questions:
            return 0 # 질문이 없으면 아무 작업도 하지 않음
        async def operation(pool, cid, cat_id, detail):
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # 다중 INSERT 쿼리 준비
                    values = []
                    for question in questions:
                        # 질문 형식 처리
                        if isinstance(question, dict):
                            question_text = question.get("question", "")
                        else:
                            question_text = str(question)

                        if question_text.strip():
                            values.append((
                                contract_id,
                                contract_category_id,
                                question_text,
                                datetime.now()
                            ))

                    if values:
                        # 배치 INSERT 실행
                        await cur.execute(
                            "DELETE FROM question WHERE contract_id = %s", (contract_id,)
                        )
                        sql = """
                              INSERT INTO question
                                  (contract_id, contract_category_id, question_detail, created_at)
                              VALUES (%s, %s, %s, %s) \
                              """
                        await cur.executemany(sql, values)
                        logger.info(f"[{contract_id}] {len(values)}개 질문 일괄 저장 완료")
                        return len(values)

                    return 0

        return await self.with_retry(operation, contract_id, contract_category_id, questions)

    async def delete_contract_data(self, contract_id: int) -> None:
        """계약서에 속한 질문·조항 삭제 (분석 실패 시 정리용)"""
        async def operation(pool, cid):
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("DELETE FROM question WHERE contract_id = %s", (cid,))
                    await cur.execute("DELETE FROM clause WHERE contract_id = %s", (cid,))

            return await self.with_retry(operation, contract_id)

    def _convert_to_clause_type(self, type_str: str) -> ClauseType:
        """문자열을 ClauseType Enum으로 변환"""
        type_mapping = {
            'standard': ClauseType.STANDARD,
            'special': ClauseType.SPECIAL,
        }
        return type_mapping.get(type_str.lower(), ClauseType.STANDARD)


    async def with_retry(self, operation_func, *args, **kwargs):
        """재시도 로직이 포함된 DB 작업 수행 헬퍼 함수"""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                if not self.pool:
                    await self.connect()

                return await operation_func(self.pool, *args, **kwargs)

            except (pymysql.err.OperationalError, asyncio.exceptions.CancelledError) as e:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"MySQL 연결 오류 최대 재시도 횟수 초과: {e}")
                    raise

                logger.warning(f"MySQL 연결 오류 ({retry_count}/{max_retries}), 재연결 시도: {e}")

                # 기존 연결 풀 정리
                if self.pool:
                    self.pool.close()
                    await self.pool.wait_closed()
                    self.pool = None

                # 지수 백오프로 대기
                await asyncio.sleep(2 ** retry_count)

        return None  # 정적 분석을 위한 반환 (실제로는 실행되지 않음)

# MySQL 클라이언트 인스턴스 생성
mysql_manager = MySQLManager()
