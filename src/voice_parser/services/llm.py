from openai import AsyncOpenAI
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from voice_parser.core.settings import OpenAISettings, get_openai_settings


class VoiceNoteAnalysis(BaseModel):
    summary: str = Field(
        description="A concise summary of the main points discussed in the voice note"
    )
    topics: List[str] = Field(
        description="List of key topics, themes, or subjects mentioned in the voice note"
    )
    action_items: List[str] = Field(
        description="Specific tasks, next steps, or actionable items mentioned in the voice note"
    )
    sentiment: Literal["positive", "neutral", "negative"] = Field(
        description="Overall emotional tone and sentiment of the voice note"
    )


class LLMClient:
    def __init__(self, settings: Optional[OpenAISettings] = None):
        if settings is None:
            settings = get_openai_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def structure_text(self, transcribed_text: str) -> VoiceNoteAnalysis:
        completion = await self.client.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "system",
                    "content": "You are an assistant that analyzes voice note transcriptions and extracts structured information. Extract summary, topics, action items, and sentiment from the text."
                },
                {
                    "role": "user",
                    "content": f"Analyze this voice note transcription:\n\n{transcribed_text}"
                }
            ],
            response_format=VoiceNoteAnalysis
        )

        # Check for refusal
        if completion.choices[0].message.refusal:
            raise ValueError(f"LLM refused request: {completion.choices[0].message.refusal}")

        # Return the automatically parsed Pydantic object
        return completion.choices[0].message.parsed