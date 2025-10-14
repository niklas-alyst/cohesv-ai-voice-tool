from io import BytesIO
from openai import AsyncOpenAI
from typing import Optional
from voice_parser.core.settings import OpenAISettings


class TranscriptionClient:
    def __init__(self, settings: Optional[OpenAISettings] = None):
        if settings is None:
            settings = OpenAISettings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def transcribe(self, audio_data: bytes, filename: str) -> str:
        # Create a file-like object from bytes
        audio_file = BytesIO(audio_data)
        audio_file.name = filename

        transcription = await self.client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        return transcription.text
