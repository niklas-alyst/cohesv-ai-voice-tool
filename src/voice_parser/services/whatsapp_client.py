import httpx
from typing import Optional
from voice_parser.core.settings import WhatsAppSettings, get_whatsapp_settings


class WhatsAppClient:
    def __init__(self, settings: Optional[WhatsAppSettings] = None):
        if settings is None:
            settings = get_whatsapp_settings()
        self.access_token = settings.whatsapp_access_token
        self.business_phone_number_id = settings.whatsapp_business_phone_number_id
        self.base_url = "https://graph.facebook.com/v17.0"

    async def get_media_url(self, media_id: str) -> str:
        url = f"{self.base_url}/{media_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["url"]

    async def download_media(self, media_id: str) -> bytes:
        media_url = await self.get_media_url(media_id)
        headers = {"Authorization": f"Bearer {self.access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(media_url, headers=headers)
            response.raise_for_status()
            return response.content

    async def send_message(self, recipient_phone: str, body: str) -> dict:
        """
        Send a text message to a WhatsApp number.

        Args:
            recipient_phone: WhatsApp phone number of the recipient (in international format without +)
            body: Text message body

        Returns:
            dict: Response from WhatsApp API
        """
        url = f"{self.base_url}/{self.business_phone_number_id}/messages"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": body
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
