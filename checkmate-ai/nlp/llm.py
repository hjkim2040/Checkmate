import threading
from typing import Dict, Any

from langchain_openai import ChatOpenAI

from config.settings import (
    OPENAI_API_KEY, LLM_TIMEOUT_SECONDS
)
from utils.logging import setup_logger

logger = setup_logger(__name__)


class LLMManager:
    """싱글톤 패턴을 사용한 LLM 관리자"""
    _instance = None
    _lock = threading.Lock()
    _models: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def get_model(self, temperature: float = 0.0):
        """캐시된 모델 가져오기 또는 새로 생성"""
        cache_key = f"{temperature}"

        if cache_key not in self._models:
            with self._lock:
                if cache_key not in self._models:  # Double-check
                    self._models[cache_key] = self._create_model(temperature)
                    logger.info(f"새 모델 생성: {cache_key}")

        return self._models[cache_key]

    def _create_model(self, temperature: float):
        """실제 모델 생성"""
        logger.info(f"LLM 모델 초기화 temperature: {temperature}")

        try:
            if not OPENAI_API_KEY:
                raise ValueError("OpenAI API 키가 설정되지 않았습니다.")

            llm = ChatOpenAI(
                model="gpt-4.1",
                api_key=OPENAI_API_KEY,
                temperature=temperature,
                max_tokens=4000,
                max_retries=2,
                timeout=LLM_TIMEOUT_SECONDS,
            )
            logger.info("OpenAI 모델 로드 성공")

            return llm

        except Exception as e:
            logger.error(f"LLM 모델 로드 오류: {e}")
            raise


# 싱글톤 인스턴스
llm_manager = LLMManager()


def init_llm_model(temperature: float = 0.0):
    """LLM 모델 초기화 (싱글톤 사용)"""
    return llm_manager.get_model(temperature)
