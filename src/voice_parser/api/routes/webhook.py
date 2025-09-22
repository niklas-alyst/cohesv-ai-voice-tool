from fastapi import APIRouter

from voice_parser.services.whatsapp_client import whatsapp_client
from voice_parser.services.storage import s3_service
from voice_parser.services.transcription import whisper_client
from voice_parser.services.llm import llm_client

router = APIRouter()


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(payload: dict):
    try:
        # Extract media_id from webhook payload
        entry = payload["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
        message = value["messages"][0]

        if message["type"] == "audio":
            media_id = message["audio"]["id"]

            # Download audio from WhatsApp
            audio_data = await whatsapp_client.download_media(media_id)

            # Upload to S3
            s3_key = await s3_service.upload_audio(audio_data, f"{media_id}.ogg")

            # Download from S3 for transcription
            audio_data = await s3_service.download_audio(s3_key)

            # Transcribe audio
            transcribed_text = await whisper_client.transcribe(audio_data, f"{media_id}.ogg")

            # Structure the transcription with LLM
            structured_analysis = await llm_client.structure_text(transcribed_text)

            return {
                "status": "ok",
                "s3_key": s3_key,
                "transcription": transcribed_text,
                "analysis": structured_analysis.model_dump()
            }

        return {"status": "ignored", "reason": "not an audio message"}

    except Exception as e:
        return {"status": "error", "error": str(e)}