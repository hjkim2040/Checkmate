import httpx

from config.settings import WEBHOOK_API_KEY, SPRINGBOOT_WEBHOOK_URL
from utils.logging import setup_logger

logger = setup_logger(__name__)

async def send_webhook_notification(
        job_id: str,
        contract_id: int,
        contract_category_id: int,
        status: str,
        result_type: str
):
    """Spring Boot에 웹훅 전송"""
    webhook_url = SPRINGBOOT_WEBHOOK_URL

    payload = {
        "contractId": contract_id,
        "contractCategoryId": contract_category_id,
        "status": status,
        "type": result_type
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": WEBHOOK_API_KEY  # 보안을 위한 API 키
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                webhook_url,
                json=payload,
                timeout=10.0,
                headers=headers
            )
            response.raise_for_status()
            logger.info(f"웹훅 전송 성공: {job_id}")
        except Exception as e:
            logger.error(f"웹훅 전송 실패: {e}")

