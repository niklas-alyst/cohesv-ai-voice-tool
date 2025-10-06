"""
AWS Lambda function for processing WhatsApp voice messages from SQS queue.

This worker function:
1. Receives messages from SQS containing WhatsApp webhook payloads
2. Downloads audio files from WhatsApp
3. Uploads to S3 for persistence
4. Transcribes audio using Whisper API
5. Structures the transcription using LLM
"""

import json
import logging
from typing import Any, Dict

from voice_parser.models import WhatsAppWebhookPayload
from voice_parser.services.whatsapp_client import WhatsAppClient
from voice_parser.services.storage import S3StorageService
from voice_parser.services.transcription import TranscriptionClient
from voice_parser.services.llm import LLMClient

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


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
    # Extract message
    message = payload.get_first_message()
    if not message:
        logger.warning("No message found in payload")
        return {"status": "ignored", "reason": "no message in payload"}

    # Check if it's an audio message
    if message.type != "audio":
        logger.info(f"Ignoring non-audio message type: {message.type}")
        return {"status": "ignored", "reason": f"not an audio message (type: {message.type})"}

    # Extract media ID
    media_id = payload.get_media_id()
    if not media_id:
        logger.error("Audio message missing media ID")
        return {"status": "error", "reason": "missing media ID"}

    logger.info(f"Processing audio message with media_id: {media_id}")

    # Initialize service clients
    whatsapp_client = WhatsAppClient()
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

    # TODO: Save to database (not yet implemented)
    logger.info(f"Processing complete for {media_id}")

    return {
        "status": "success",
        "media_id": media_id,
        "s3_key": s3_key,
        "transcription_length": len(transcribed_text),
        "analysis": structured_analysis.model_dump()
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for SQS events containing WhatsApp webhook payloads.

    Args:
        event: SQS event with Records
        context: Lambda context object

    Returns:
        dict: Processing result with batchItemFailures for partial failures
    """
    import asyncio

    logger.info(f"Received SQS event with {len(event.get('Records', []))} records")

    batch_item_failures = []

    for record in event.get("Records", []):
        message_id = record.get("messageId")

        try:
            # Parse SQS message body
            body = record.get("body", "")
            payload_dict = json.loads(body)

            # Validate and parse WhatsApp payload
            payload = WhatsAppWebhookPayload.model_validate(payload_dict)

            # Process the message
            result = asyncio.run(process_message(payload))

            logger.info(f"Message {message_id} processed: {result['status']}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message {message_id}: {e}")
            # Don't retry malformed messages
            continue

        except Exception as e:
            logger.error(f"Failed to process message {message_id}: {e}", exc_info=True)
            # Add to batch failures for retry
            batch_item_failures.append({"itemIdentifier": message_id})

    # Return batch item failures for SQS to retry
    return {"batchItemFailures": batch_item_failures}
