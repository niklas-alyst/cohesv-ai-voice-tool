import httpx
from typing import Optional
from voice_parser.core.settings import TwilioWhatsAppSettings
import logging

logger = logging.getLogger(__name__)


class TwilioWhatsAppClient:
    def __init__(self, settings: Optional[TwilioWhatsAppSettings] = None):
        if settings is None:
            settings = TwilioWhatsAppSettings()
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.from_number = settings.twilio_whatsapp_number
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"
        self.auth = (self.account_sid, self.auth_token)

    async def download_media(self, media_url: str) -> bytes:
        """
        Download media from Twilio media URL.

        Args:
            media_url: Full Twilio media URL from webhook payload

        Returns:
            bytes: Media file content
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(media_url, auth=self.auth)
            response.raise_for_status()
            return response.content

    async def send_message(self, recipient_phone: str, body: str) -> dict:
        """
        Send a text message to a WhatsApp number via Twilio.

        Args:
            recipient_phone: WhatsApp phone number in format "whatsapp:+1234567890"
            body: Text message body

        Returns:
            dict: Response from Twilio API
        """
        # Ensure recipient_phone has whatsapp: prefix
        if not recipient_phone.startswith("whatsapp:"):
            recipient_phone = f"whatsapp:{recipient_phone}"

        url = f"{self.base_url}/Messages.json"
        payload = {
            "From": self.from_number,
            "To": recipient_phone,
            "Body": body
        }

        logger.info(f"Sending POST to url {url} with payload {payload}")
        logger.info("Dummy implementation, nothing sent")
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(url, data=payload, auth=self.auth)
        #     response.raise_for_status()
        #     return response.json()
