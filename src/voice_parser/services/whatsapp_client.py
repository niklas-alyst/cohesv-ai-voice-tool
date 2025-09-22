import httpx
from typing import Optional
from voice_parser.core.settings import WhatsAppSettings, get_whatsapp_settings


class WhatsAppClient:
    def __init__(self, settings: Optional[WhatsAppSettings] = None):
        if settings is None:
            settings = get_whatsapp_settings()
        self.access_token = settings.whatsapp_access_token
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
