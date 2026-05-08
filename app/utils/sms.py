import httpx
from config import settings
import logging

logger = logging.getLogger(__name__)


async def send_sms(phone: str, message: str) -> bool:
    """
    Eskiz.uz orqali SMS yuborish.
    SMS_PROVIDER_URL, SMS_USERNAME, SMS_PASSWORD .env da sozlanishi kerak.
    """
    if not settings.SMS_PROVIDER_URL:
        logger.warning(f"[SMS MOCK] → {phone}: {message}")
        return True  # Development rejimida log ga yozamiz

    try:
        # 1. Token olish
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                f"{settings.SMS_PROVIDER_URL}/auth/login",
                json={"email": settings.SMS_USERNAME, "password": settings.SMS_PASSWORD}
            )
            token_resp.raise_for_status()
            token = token_resp.json().get("data", {}).get("token")

            if not token:
                logger.error("SMS token olinmadi")
                return False

            # 2. SMS yuborish
            sms_resp = await client.post(
                f"{settings.SMS_PROVIDER_URL}/message/sms/send",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "mobile_phone": phone.replace("+", ""),
                    "message": message,
                    "from": settings.SMS_FROM,
                }
            )
            sms_resp.raise_for_status()
            logger.info(f"SMS yuborildi → {phone}")
            return True

    except Exception as e:
        logger.error(f"SMS xatolik ({phone}): {e}")
        return False


def build_debt_reminder_message(debtor_name: str, amount: float, due_date: str) -> str:
    return (
        f"Hurmatli {debtor_name}! "
        f"Ertaga {due_date} sanasida {amount:,.0f} so'm qarz to'lash muddati. "
        f"Iltimos, o'z vaqtida to'lang."
    )