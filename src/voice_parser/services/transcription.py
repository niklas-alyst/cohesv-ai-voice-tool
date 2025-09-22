from openai import AsyncOpenAI
from typing import Optional
from voice_parser.core.config import OpenAISettings, get_openai_settings


class WhisperClient:
    def __init__(self, settings: Optional[OpenAISettings] = None):
        if settings is None:
            settings = get_openai_settings()
        self.client = AsyncOpenAI(api_key=settings.whisper_api_key)

    async def transcribe(self, audio_data: bytes, filename: str) -> str:
        # Create a file-like object from bytes
        from io import BytesIO
        audio_file = BytesIO(audio_data)
        audio_file.name = filename

        transcription = await self.client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        return transcription.text


whisper_client = WhisperClient()