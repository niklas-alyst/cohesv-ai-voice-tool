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
from voice_parser.services.whatsapp_client import WhatsAppClient
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
    # Initialize WhatsApp client first (needed for sending responses)
    whatsapp_client = WhatsAppClient()

    # Extract message
    message = payload.get_first_message()
    if not message:
        logger.warning("No message found in payload")
        return {"status": "ignored", "reason": "no message in payload"}

    # Get message's phone number
    message_phonenumber = payload.get_phonenumber()
    if not message_phonenumber:
        logger.error("Could not extract sender phone number")
        return {"status": "error", "reason": "missing sender phone number"}

    # Check if it's an audio message
    if message.type != "audio":
        logger.info(f"Ignoring non-audio message type: {message.type}")
        # Send response to user
        await whatsapp_client.send_message(
            recipient_phone=message_phonenumber,
            body="Text messages are not supported, please send audio"
        )
        return {"status": "ignored", "reason": f"not an audio message (type: {message.type})"}

    # Extract media ID
    media_id = payload.get_media_id()
    if not media_id:
        logger.error("Audio message missing media ID")
        return {"status": "error", "reason": "missing media ID"}

    logger.info(f"Processing audio message with media_id: {media_id}")

    # Initialize other service clients
    s3_service = S3StorageService()
    transcription_client = TranscriptionClient()
    llm_client = LLMClient()

    # Download audio from WhatsApp
    logger.info(f"Downloading audio from WhatsApp: {media_id}")
    audio_data = await whatsapp_client.download_media(media_id)

    # Upload to S3 for persistence
    s3_key = await s3_service.upload_audio(audio_data, f"{media_id}.ogg")
    logger.info(f"Uploaded to S3: {s3_key}")

    # Download from S3 for transcription
    audio_data = await s3_service.download(s3_key)

    # Transcribe audio
    logger.info(f"Transcribing audio: {media_id}")
    transcribed_text = await transcription_client.transcribe(audio_data, f"{media_id}.ogg")
    logger.info(f"Transcription completed: {len(transcribed_text)} characters")

    # Structure the transcription with LLM
    logger.info(f"Structuring transcription with LLM: {media_id}")
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

    logger.info(f"Processing complete for {media_id}")

    return {
        "status": "success",
        "media_id": media_id,
        "s3_key": s3_key,
        "transcription_length": len(transcribed_text),
        "analysis": structured_analysis.model_dump()
    }
