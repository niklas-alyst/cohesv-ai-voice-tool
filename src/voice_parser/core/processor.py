"""
Core message processing logic for WhatsApp voice messages.

This module contains the business logic for processing WhatsApp voice messages:
1. Validates message type and extracts media ID
2. Downloads audio files from WhatsApp
3. Uploads to S3 for persistence
4. Transcribes audio using Whisper API
5. Structures the transcription using LLM
"""

import logging
from typing import Any, Dict

from voice_parser.models import WhatsAppWebhookPayload
from voice_parser.services.twilio_whatsapp_client import TwilioWhatsAppClient
from voice_parser.services.storage import S3StorageService
from voice_parser.services.transcription import TranscriptionClient
from voice_parser.services.llm import LLMClient

logger = logging.getLogger(__name__)


async def process_message(payload: WhatsAppWebhookPayload) -> Dict[str, Any]:
    """
    Process a single WhatsApp message.

    Args:
        payload: Parsed WhatsApp webhook payload

    Returns:
        dict: Processing result with status and details

    Raises:
        Exception: If processing fails
    """
    # Initialize Twilio WhatsApp client first (needed for sending responses)
    whatsapp_client = TwilioWhatsAppClient()

    # Get message's phone number
    message_phonenumber = payload.get_phone_number()
    if not message_phonenumber:
        logger.error("Could not extract sender phone number")
        return {"status": "error", "reason": "missing sender phone number"}

    logger.info(f"Received message from {message_phonenumber}")

    # Check if it's an audio message
    message_type = payload.get_message_type()
    if message_type != "audio":
        logger.info(f"Ignoring non-audio message type: {message_type}")
        # Send response to user
        await whatsapp_client.send_message(
            recipient_phone=message_phonenumber,
            body="Text messages are not supported, please send audio"
        )
        return {"status": "ignored", "reason": f"not an audio message (type: {message_type})"}

    # Extract media URL
    media_url = payload.get_media_url()
    if not media_url:
        logger.error("Audio message missing media URL")
        return {"status": "error", "reason": "missing media URL"}

    # Use MessageSid as unique identifier for files
    message_id = payload.MessageSid
    logger.info(f"Processing audio message: {message_id}")

    # Initialize other service clients
    s3_service = S3StorageService()
    transcription_client = TranscriptionClient()
    llm_client = LLMClient()

    # Download audio from Twilio
    logger.info(f"Downloading audio from Twilio: {message_id}")
    audio_data = await whatsapp_client.download_media(media_url)

    # Upload to S3 for persistence
    s3_key = await s3_service.upload_audio(audio_data, f"{message_id}.ogg")
    logger.info(f"Uploaded to S3: {s3_key}")

    # Download from S3 for transcription
    audio_data = await s3_service.download(s3_key)

    # Transcribe audio
    logger.info(f"Transcribing audio: {message_id}")
    transcribed_text = await transcription_client.transcribe(audio_data, f"{message_id}.ogg")
    logger.info(f"Transcription completed: {len(transcribed_text)} characters")

    # Structure the transcription with LLM
    logger.info(f"Structuring transcription with LLM: {message_id}")
    structured_analysis = await llm_client.structure_text(transcribed_text)

    # Format structured analysis for WhatsApp message
    formatted_text = f"""*Summary:*
{structured_analysis.summary}

*Topics:*
{chr(10).join(f'• {topic}' for topic in structured_analysis.topics)}

*Action Items:*
{chr(10).join(f'• {item}' for item in structured_analysis.action_items)}

*Sentiment:* {structured_analysis.sentiment}"""

    # Save to database 
    await s3_service.upload_text(formatted_text, filename=f"{s3_key}_summary.txt")
    
    # Send structured analysis back to user
    logger.info(f"Sending structured analysis to {message_phonenumber}")
    await whatsapp_client.send_message(
        recipient_phone=message_phonenumber,
        body=f"Structured text: {formatted_text}"
    )

    logger.info(f"Processing complete for {message_id}")

    return {
        "status": "success",
        "message_id": message_id,
        "s3_key": s3_key,
        "transcription_length": len(transcribed_text),
        "analysis": structured_analysis.model_dump()
    }
