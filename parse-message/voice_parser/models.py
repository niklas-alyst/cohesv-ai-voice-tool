"""Pydantic models for Twilio WhatsApp webhook payloads."""

from typing import Optional, Literal
from pydantic import BaseModel


class TwilioWebhookPayload(BaseModel):
    """Twilio WhatsApp webhook payload.

    Twilio sends a flat structure with form-encoded data.
    See: https://www.twilio.com/docs/messaging/guides/webhook-request
    """

    # Message identifiers
    MessageSid: str
    SmsSid: Optional[str] = None
    SmsMessageSid: Optional[str] = None
    AccountSid: str

    # Sender information
    From: str  # Format: "whatsapp:+14155552671"
    To: str    # Format: "whatsapp:+15551238886"
    ProfileName: Optional[str] = None
    WaId: Optional[str] = None  # WhatsApp ID without prefix

    # Message content
    Body: Optional[str] = None
    MessageType: Optional[str] = None

    # Media information
    NumMedia: str = "0"  # String number of media attachments
    MediaContentType0: Optional[str] = None
    MediaUrl0: Optional[str] = None
    MediaContentType1: Optional[str] = None
    MediaUrl1: Optional[str] = None

    # Status and metadata
    SmsStatus: Optional[str] = None
    ApiVersion: Optional[str] = None
    NumSegments: Optional[str] = None
    ReferralNumMedia: Optional[str] = None
    ChannelMetadata: Optional[str] = None

    class Config:
        # Allow extra fields that Twilio might send
        extra = "allow"

    def get_message_type(self) -> Literal["text", "audio", "image", "video", "document", "unknown"]:
        """Determine message type based on media content type."""
        if self.MessageType:
            # Map Twilio's MessageType to our internal types
            msg_type = self.MessageType.lower()
            if msg_type in ["text", "audio", "image", "video", "document"]:
                return msg_type
            if msg_type == "file":  # Twilio might use 'file'
                return "document"

        # Fallback for older webhook formats
        if int(self.NumMedia) == 0:
            return "text"

        if self.MediaContentType0:
            content_type = self.MediaContentType0.lower()
            if content_type.startswith("audio/"):
                return "audio"
            elif content_type.startswith("image/"):
                return "image"
            elif content_type.startswith("video/"):
                return "video"
            else:
                return "document"

        return "unknown"

    def get_media_url(self) -> Optional[str]:
        """Extract the first media URL (typically for audio messages)."""
        if int(self.NumMedia) > 0:
            return self.MediaUrl0
        return None

    def get_phone_number(self) -> str:
        """Extract sender's phone number (with whatsapp: prefix)."""
        return self.From

    def get_phone_number_without_prefix(self) -> str:
        """Extract sender's phone number without whatsapp: prefix."""
        # Remove "whatsapp:" prefix if present
        return self.From.replace("whatsapp:", "")


# Keep old name for backwards compatibility during migration
WhatsAppWebhookPayload = TwilioWebhookPayload
