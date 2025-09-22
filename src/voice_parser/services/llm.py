import httpx
from typing import List
from pydantic import BaseModel
from voice_parser.core.config import settings


class VoiceNoteAnalysis(BaseModel):
    summary: str
    topics: List[str]
    action_items: List[str]
    sentiment: str


class LLMClient:
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.base_url = "https://api.openai.com/v1/chat/completions"

    async def structure_text(self, transcribed_text: str) -> VoiceNoteAnalysis:
        async with httpx.AsyncClient() as client:
            payload = {
                "model": "gpt-4o-2024-08-06",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an assistant that analyzes voice note transcriptions and extracts structured information. Extract summary, topics, action items, and sentiment from the text."
                    },
                    {
                        "role": "user",
                        "content": f"Analyze this voice note transcription:\n\n{transcribed_text}"
                    }
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "voice_note_analysis",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "summary": {
                                    "type": "string",
                                    "description": "Brief summary of the voice note"
                                },
                                "topics": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of main topics discussed"
                                },
                                "action_items": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of action items or tasks mentioned"
                                },
                                "sentiment": {
                                    "type": "string",
                                    "description": "Overall sentiment of the voice note",
                                    "enum": ["positive", "neutral", "negative"]
                                }
                            },
                            "required": ["summary", "topics", "action_items", "sentiment"],
                            "additionalProperties": False
                        }
                    }
                }
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            response = await client.post(
                self.base_url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()

            # Check for refusal
            if result["choices"][0]["message"].get("refusal"):
                raise ValueError(f"LLM refused request: {result['choices'][0]['message']['refusal']}")

            # Parse the structured response
            content = result["choices"][0]["message"]["content"]
            import json
            data = json.loads(content)
            return VoiceNoteAnalysis(**data)


llm_client = LLMClient()