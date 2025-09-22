import httpx
from voice_parser.core.config import settings


class WhisperClient:
    def __init__(self):
        self.api_key = settings.whisper_api_key
        self.base_url = "https://api.openai.com/v1/audio/transcriptions"

    async def transcribe(self, audio_data: bytes, filename: str) -> str:
        async with httpx.AsyncClient() as client:
            files = {
                "file": (filename, audio_data, "audio/ogg")
            }
            data = {
                "model": "whisper-1"
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }

            response = await client.post(
                self.base_url,
                files=files,
                data=data,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            return result["text"]


whisper_client = WhisperClient()