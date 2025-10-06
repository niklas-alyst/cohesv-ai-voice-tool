"""Pydantic models for WhatsApp webhook payloads."""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class Profile(BaseModel):
    """Contact profile information."""

    name: str


class Contact(BaseModel):
    """Contact information from WhatsApp webhook."""

    profile: Profile
    wa_id: str


class AudioMessage(BaseModel):
    """Audio message details."""

    id: str
    mime_type: str
    sha256: str
    voice: bool


class TextMessage(BaseModel):
    """Text message details."""

    body: str


class Metadata(BaseModel):
    """Metadata about the WhatsApp business account."""

    display_phone_number: str
    phone_number_id: str


class Message(BaseModel):
    """Individual message from WhatsApp."""

    from_: str = Field(alias="from")
    id: str
    timestamp: str
    type: Literal["text", "audio", "image", "video", "document", "voice"]
    text: Optional[TextMessage] = None
    audio: Optional[AudioMessage] = None


class Value(BaseModel):
    """Value object containing message details."""

    messaging_product: str
    metadata: Metadata
    contacts: list[Contact]
    messages: list[Message]


class Change(BaseModel):
    """Change object in webhook payload."""

    value: Value
    field: str


class Entry(BaseModel):
    """Entry object in webhook payload."""

    id: str
    changes: list[Change]


class WhatsAppWebhookPayload(BaseModel):
    """Top-level WhatsApp webhook payload."""

    object: Literal["whatsapp_business_account"]
    entry: list[Entry]

    def get_first_message(self) -> Optional[Message]:
        """Extract the first message from the payload."""
        try:
            return self.entry[0].changes[0].value.messages[0]
        except (IndexError, AttributeError):
            return None

    def get_media_id(self) -> Optional[str]:
        """Extract media ID from audio message."""
        message = self.get_first_message()
        if message and message.type == "audio" and message.audio:
            return message.audio.id
        return None

    def get_phonenumber(self) -> Optional[str]:
        """Extract sender's phone number from the message."""
        message = self.get_first_message()
        if message:
            return message.from_
        return None
