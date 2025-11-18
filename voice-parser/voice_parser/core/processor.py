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

from ai_voice_shared import TwilioWebhookPayload
from ai_voice_shared.services.s3_service import S3Service
from voice_parser.services.twilio_whatsapp_client import TwilioWhatsAppClient
from voice_parser.services.transcription import TranscriptionClient
from voice_parser.services.llm import LLMClient, MessageIntent
from ai_voice_shared import CustomerLookupClient


logger = logging.getLogger(__name__)


async def process_message(payload: TwilioWebhookPayload) -> Dict[str, Any]:
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
        raise ValueError("Could not extract sender phone number")
    

    customer_lookup_client = CustomerLookupClient()
    customer_metadata = await customer_lookup_client.fetch_customer_metadata(message_phonenumber)
    company_id = customer_metadata.company_id

    message_type = payload.get_message_type()
    message_id = payload.MessageSid
    logger.info(f"Received message of type {message_type} from {message_phonenumber}")

    # Send confirmation back to client
    confirmation_response = await whatsapp_client.send_message(
        recipient_phone=message_phonenumber,
        body="Message received, processing..."
    )
    logger.info(f"Sent confirmation message, Twilio SID: {confirmation_response.get('sid')}, Status: {confirmation_response.get('status')}")

    # Initialize other service clients
    s3_service = S3Service()
    llm_client = LLMClient()

    if message_type == "text":
        full_text = payload.Body

    elif message_type == "audio":
        # Extract media URL
        media_url = payload.get_media_url()
        if not media_url:
            raise ValueError("Audio message missing media URL")

        logger.info(f"Processing audio message: {message_id}")

        transcription_client = TranscriptionClient()

        # Download audio from Twilio
        logger.info(f"Downloading audio from Twilio: {message_id}")
        audio_data = await whatsapp_client.download_media(media_url)

        # Transcribe audio
        logger.info(f"Transcribing audio: {message_id}")
        full_text = await transcription_client.transcribe(audio_data, filename=f"{message_id}.ogg")
        logger.info(f"Transcription completed: {len(full_text)} characters")

    else:
        logger.info(f"Ignoring message type: {message_type}")
        # Send response to user
        await whatsapp_client.send_message(
            recipient_phone=message_phonenumber,
            body=f"Messages of type {message_type} are not supported, please send text/audio. Full payload: {payload.model_dump()}"
        )
        return {"status": "ignored", "reason": f"incorrect message type: {message_type}"}

    # Structure the text with LLM
    logger.info(f"Structuring text with LLM: {message_id}")

    message_metadata = await llm_client.extract_message_metadata(full_text)

    if message_metadata.intent in (MessageIntent.JOB_TO_BE_DONE, MessageIntent.KNOWLEDGE_DOCUMENT):
        structured_analysis = await llm_client.structure_full_text(full_text, message_metadata.intent)
    elif message_metadata.intent == MessageIntent.OTHER:
        structured_analysis = None

    # Upload artifacts to S3
    key_prefix = f"{company_id}/{message_metadata.intent.value}/{message_metadata.tag}_{message_id}"

    s3_keys = {}
    if message_type == "audio":
        # Upload to S3 for persistence
        s3_audio_key = await s3_service.upload(
            data=audio_data,
            key=f"{key_prefix}_audio.ogg",
            content_type="audio/ogg",
            overwrite=False,
        )
        s3_keys["audio"] = s3_audio_key
        logger.info(f"Uploaded audio to S3: {s3_audio_key}")

    # Upload analysed text
    s3_full_text_key = await s3_service.upload(
        data=full_text.encode("utf-8"),
        key=f"{key_prefix}_full_text.txt",
        content_type="text/plain",
        overwrite=False,
    )
    s3_keys["full_text"] = s3_full_text_key
    logger.info(f"Uploaded text to analyze to S3: {s3_full_text_key}")

    # Format structured analysis for WhatsApp message
    if structured_analysis:
        formatted_text = structured_analysis.format()

        # Save to database
        s3_text_summary_key = await s3_service.upload(
            data=formatted_text.encode("utf-8"),
            key=f"{key_prefix}.text_summary.txt",
            content_type="text/plain",
            overwrite=False,
        )
        s3_keys["text_summary"] = s3_text_summary_key

        # Send structured analysis back to user
        logger.info(f"Sending structured analysis to {message_phonenumber}")
        message_body = f"""Successfully ingested the following items:

{formatted_text}

Note: Replies to this message are treated as new requests.
"""
        analysis_response = await whatsapp_client.send_message(
            recipient_phone=message_phonenumber,
            body=message_body
        )
        logger.info(f"Sent analysis message, Twilio SID: {analysis_response.get('sid')}, Status: {analysis_response.get('status')}")
    else:
        # For OTHER intent messages, send a simple confirmation
        logger.info("Message classified as OTHER intent, sending simple confirmation")
        await whatsapp_client.send_message(
            recipient_phone=message_phonenumber,
            body="Message received and processed. Note: This message was classified as informational only."
        )

    logger.info(f"Processing complete for {message_id}")

    return {
        "status": "success",
        "message_id": message_id,
        "s3_keys": s3_keys,
        "transcription_length": len(full_text),
        "metadata": message_metadata.model_dump(),
        "analysis": structured_analysis.model_dump() if structured_analysis else None
    }
