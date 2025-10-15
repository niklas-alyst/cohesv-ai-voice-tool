from openai import AsyncOpenAI
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from voice_parser.core.settings import OpenAISettings


SYSTEM_MESSAGE = """
You are assisting workers of a plumbing business to extract structured information from voice notes.

While on-site, these workers may get information about a new job, understand tasks they need to do etc., or similar.
The business has a job and project management software for managing all of this information
but it's difficult to remember all of it and the workers don't have access to the computer while on site.

This is where you come in. The workers will send a voice note to you, the text from this will be transcribed, and
you should extract all the relevant information from the transcription. 
so that it's easy for an assistant to enter it into the software.

For example, this could be
- remember to purchase material for a given job 
- put this date into the calendar
- check with builders or clients when they're ready

Please extract summary, the job this is about, the context for the action items, and ALL action items mentioned.

IMPORTANT: it's CRITICAL that you don't infer any items from the message. Only capture what is explicitly said!
"""

class VoiceNoteAnalysis(BaseModel):
    summary: str = Field(
        description="A concise summary of the main point in the note"
    )
    job: str = Field(
        description="The specific job this is related to"
    )
    context: str = Field(
        description="The background to why these action items should be done."
    )
    action_items: List[str] = Field(
        description="Specific tasks, next steps, and items to be added to be registered."
    )


class LLMClient:
    def __init__(self, settings: Optional[OpenAISettings] = None):
        if settings is None:
            settings = OpenAISettings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def structure_text(self, transcribed_text: str) -> VoiceNoteAnalysis:
        completion = await self.client.chat.completions.parse(
            model="gpt-5-nano-2025-08-07",
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_MESSAGE
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