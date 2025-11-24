"""Shared data models for AI Voice Tool services."""

from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict


class CustomerMetadata(BaseModel):
    """Customer metadata returned from the customer lookup service."""

    customer_id: str
    company_id: str
    company_name: str


class S3ObjectMetadata(BaseModel):
    """Metadata for an S3 object."""

    key: str
    etag: str
    size: int
    last_modified: str  # ISO 8601 format


class S3ListResponse(BaseModel):
    """Response from S3 list_objects operation with pagination support."""

    files: list[S3ObjectMetadata]
    nextContinuationToken: Optional[str] = None


class MessageIdSummary(BaseModel):
    """Summary of a message with its ID and metadata."""

    message_id: str
    tag: str
    file_count: int


class S3ListIdsResponse(BaseModel):
    """Response from S3 list_objects operation in ids-only mode."""

    message_ids: list[MessageIdSummary]
    nextContinuationToken: Optional[str] = None


class MessageArtifact(BaseModel):
    """Artifact file for a specific message."""

    key: str
    type: Literal["audio", "full_text", "text_summary"]
    etag: str
    size: int
    last_modified: str  # ISO 8601 format


class MessageArtifactsResponse(BaseModel):
    """Response containing all artifacts for a specific message."""

    message_id: str
    company_id: str
    intent: str
    tag: str
    files: list[MessageArtifact]


class TwilioWebhookPayload(BaseModel):
    """Twilio WhatsApp webhook payload.

    This model can be initialized from a standard Twilio webhook payload (a flat JSON object)
    or from an AWS API Gateway event where the payload is in a URL-encoded 'body'.
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

    model_config = ConfigDict(extra="allow")

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
        """Extract sender's phone number without either whatsapp: or + prefix"""
        # Remove "whatsapp:" and "+" prefixes if present
        phone_number = self.From.replace("whatsapp:", "")
        if phone_number.startswith("+"):
            return phone_number[1:]
        return phone_number
