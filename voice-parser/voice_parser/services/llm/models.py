import abc
import re
from pydantic import BaseModel, Field, field_validator
from typing import List
import enum

class MessageIntent(str, enum.Enum):
    """The various types of intents possible for a message"""
    JOB_TO_BE_DONE = "job-to-be-done"
    KNOWLEDGE_DOCUMENT = "knowledge-document"
    OTHER = "other"


class MessageMetadata(BaseModel):
    """Metadata extracted from a message for categorization and storage"""

    intent: MessageIntent = Field(
        description="The intent of the message - whether it's about a job to be done, permanent knowledge, or other"
    )
    tag: str = Field(
        description="A short, human-readable tag suitable for use as an S3 key prefix. Should be kebab-case (lowercase with hyphens), 2-5 words summarizing the message content"
    )

    @field_validator('tag')
    @classmethod
    def validate_s3_key(cls, v: str) -> str:
        """Ensure tag is suitable for S3 key usage"""
        # Convert to lowercase and replace spaces with hyphens
        sanitized = v.lower().strip()
        # Replace multiple spaces/hyphens with single hyphen
        sanitized = re.sub(r'[\s_]+', '-', sanitized)
        # Remove any characters that aren't alphanumeric, hyphens, or dots
        sanitized = re.sub(r'[^a-z0-9\-.]', '', sanitized)
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')

        if not sanitized:
            raise ValueError("Tag must contain at least one alphanumeric character")

        return sanitized

    @classmethod
    def get_system_message(cls) -> str:
        return """You are analyzing voice notes from workers in a plumbing business to extract metadata.

Your task is to determine:
1. The INTENT of the message:
   - "job-to-be-done": If the message is about specific tasks, action items, or work that needs to be completed
   - "knowledge-document": If the message is about storing information, documenting processes, recording facts, or general knowledge
   - "other": If the message doesn't fit either category (casual conversation, questions without actionable content, etc.)

2. A TAG that summarizes the message content:
   - Should be 2-5 words describing the main topic
   - Use kebab-case format (lowercase with hyphens)
   - Must be human-readable and descriptive
   - Examples: "bathroom-renovation-materials", "leak-repair-notes", "client-meeting-summary"

Be concise and accurate in your classification."""


class StructuredDocumentModel(abc.ABC, BaseModel):

    WHATSAPP_CHAR_LIMIT: int = 1600

    @abc.abstractmethod
    def format(self) -> str:
        """Create human-readable format"""
        pass

    @abc.abstractmethod
    def format_truncated(self) -> str:
        """Create truncated format for WhatsApp when full format exceeds limit"""
        pass

    @classmethod
    @abc.abstractmethod
    def get_system_message(cls) -> str:
        """Get system message for how to structure document"""
        pass

    def format_for_whatsapp(self, tag: str, prefix: str = "", suffix: str = "") -> str:
        """Get WhatsApp-safe message, truncating if necessary.

        Returns formatted message that fits within WhatsApp's character limit.
        Falls back to truncated format, then minimal confirmation if needed.
        """
        # Try full format first
        full_message = f"{prefix}{self.format()}{suffix}"
        if len(full_message) <= self.WHATSAPP_CHAR_LIMIT:
            return full_message

        # Try truncated format
        truncated_message = f"{prefix}{self.format_truncated()}{suffix}"
        if len(truncated_message) <= self.WHATSAPP_CHAR_LIMIT:
            return truncated_message

        # Fallback to minimal confirmation
        minimal = f"Successfully uploaded: {tag}"
        return f"{prefix}{minimal}{suffix}" if len(f"{prefix}{minimal}{suffix}") <= self.WHATSAPP_CHAR_LIMIT else minimal

class KnowledgeDocumentModel(StructuredDocumentModel): # TODO: replace fields with relevant structure
    title: str = Field(
        description="A short human-readable title"
    )
    summary: str = Field(
        description="A concise summary of the key concepts"
    )
    context: str = Field(
        description="The background and context around what this knowledge is about and when it applies"
    )

    def format(self) -> str:
        formatted_text = f"""*Title:*
{self.title}

*Summary:*
{self.summary}

*Context:*
{self.context}
"""
        return formatted_text

    def format_truncated(self) -> str:
        """Truncated format: Title and Summary only"""
        return f"""*Title:*
{self.title}

*Summary:*
{self.summary}

---
Rest of knowledge document truncated.
"""

    @classmethod
    def get_system_message(cls) -> str:
        return """You are assisting workers of trades businesses to extract structured knowledge information from voice notes and other sources.

Experienced workers have a lot of knowlege about how to do different tasks, what works and what doesn't etc.
Your job is to listen carefully to what they say or show and then document this in a concise summary.
It's also important that you capture when and how this applies - i.e. the context of this `knowledge document`.
"""


 
class JobsToBeDoneDocumentModel(StructuredDocumentModel):
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

    def format(self) -> str:
        formatted_text = f"""*Summary:*
{self.summary}

*Job:*
{self.job}

*Context:*
{self.context}

*Action Items:*
{chr(10).join(f'• {item}' for item in self.action_items)}
"""
        return formatted_text

    def format_truncated(self) -> str:
        """Truncated format: Summary and Action Items only"""
        return f"""*Summary:*
{self.summary}

*Action Items:*
{chr(10).join(f'• {item}' for item in self.action_items)}

---
Rest of job information truncated.
"""

    @classmethod
    def get_system_message(cls) -> str:
        return """You are assisting workers of a plumbing business to extract structured information from voice notes.

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

def get_structured_document_model(message_intent: MessageIntent) -> StructuredDocumentModel:
    if message_intent == MessageIntent.JOB_TO_BE_DONE:
        return JobsToBeDoneDocumentModel
    elif message_intent == MessageIntent.KNOWLEDGE_DOCUMENT:
        return KnowledgeDocumentModel
    else:
        raise ValueError(f"no structured document model exists for {message_intent}")