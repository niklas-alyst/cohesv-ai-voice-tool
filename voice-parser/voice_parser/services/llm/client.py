from openai import AsyncOpenAI
from typing import Optional
from voice_parser.core.settings import OpenAISettings
from .models import MessageIntent, MessageMetadata, StructuredDocumentModel, get_structured_document_model


class LLMClient:
    def __init__(self, settings: Optional[OpenAISettings] = None):
        if settings is None:
            settings = OpenAISettings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def extract_message_metadata(self, full_text: str) -> MessageMetadata:
        """
        Extract metadata from a message including intent and storage tag.

        Args:
            full_text: The full text content to analyze

        Returns:
            MessageMetadata containing intent classification and S3-compatible tag
        """
        completion = await self.client.chat.completions.parse(
            model="gpt-5-nano-2025-08-07",
            messages=[
                {
                    "role": "system",
                    "content": MessageMetadata.get_system_message()
                },
                {
                    "role": "user",
                    "content": f"Analyze this text:\n\n{full_text}"
                }
            ],
            response_format=MessageMetadata
        )

        # Check for refusal
        if completion.choices[0].message.refusal:
            raise ValueError(f"LLM refused request: {completion.choices[0].message.refusal}")

        # Return the automatically parsed Pydantic object
        return completion.choices[0].message.parsed

    async def structure_full_text(self, full_text: str, message_intent: MessageIntent) -> StructuredDocumentModel:
        structured_document_model = get_structured_document_model(message_intent)
        completion = await self.client.chat.completions.parse(
            model="gpt-5-nano-2025-08-07",
            messages=[
                {
                    "role": "system",
                    "content": structured_document_model.get_system_message()
                },
                {
                    "role": "user",
                    "content": f"Analyze this text:\n\n{full_text}"
                }
            ],
            response_format=structured_document_model
        )

        # Check for refusal
        if completion.choices[0].message.refusal:
            raise ValueError(f"LLM refused request: {completion.choices[0].message.refusal}")

        # Return the automatically parsed Pydantic object
        return completion.choices[0].message.parsed