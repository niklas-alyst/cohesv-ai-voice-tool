from fastapi import FastAPI
from services.whatsapp_client import whatsapp_client
from services.storage import s3_service
from services.transcription import whisper_client

app = FastAPI(title="Voice Parser", version="0.1.0")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/webhook/whatsapp")
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

            return {"status": "ok", "s3_key": s3_key, "transcription": transcribed_text}

        return {"status": "ignored", "reason": "not an audio message"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def main() -> None:
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)