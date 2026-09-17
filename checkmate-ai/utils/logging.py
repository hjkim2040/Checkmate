import logging
import os
import sys
from typing import Dict

# 로그 레벨 설정
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# 로거 캐시
_LOGGERS: Dict[str, logging.Logger] = {}


def setup_logger(name: str) -> logging.Logger:
    """
    지정된 이름으로 로거를 설정하고 반환합니다.
    콘솔 출력만 지원합니다.

    Args:
        name (str): 로거 이름

    Returns:
        logging.Logger: 설정된 로거 객체
    """
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)

    # 이미 핸들러가 설정되어 있으면 재설정하지 않음
    if logger.hasHandlers():
        logger.handlers.clear()

    # 로그 레벨 설정
    log_level = getattr(logging, LOG_LEVEL, logging.INFO)

    logger.setLevel(log_level)

    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(console_handler)

    logger.propagate = False

    _LOGGERS[name] = logger
    return logger


# 기본 로거 설정
default_logger = setup_logger('AI_analyze')
