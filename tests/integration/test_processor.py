import pytest
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from unittest.mock import AsyncMock, patch, MagicMock
from voice_parser.models import WhatsAppWebhookPayload
from voice_parser.core.processor import process_message
from voice_parser.services.storage import S3StorageService
from voice_parser.core.settings import S3Settings


@pytest.fixture(scope="session", autouse=True)
def load_test_env():
    """Load test environment variables from .env.test"""
    load_dotenv(".env.test")


@pytest.fixture
def test_s3_settings():
    """Create S3 settings using test environment variables"""
    return S3Settings(
        aws_region=os.getenv("AWS_REGION"),
        s3_bucket_name=os.getenv("S3_BUCKET_NAME"),
        s3_bucket_prefix=os.getenv("S3_BUCKET_PREFIX"),
    )


@pytest.fixture
def storage_service(test_s3_settings):
    """Create storage service with test settings"""
    return S3StorageService(settings=test_s3_settings)


@pytest.fixture
def text_payload():
    """Load text message webhook payload"""
    test_dir = Path(__file__).parent.parent
    payload_file = test_dir / "fixtures" / "webhook_payload_text.json"

    with open(payload_file, "r") as f:
        payload_data = json.load(f)

    return WhatsAppWebhookPayload(**payload_data)


@pytest.fixture
def audio_payload():
    """Load audio message webhook payload"""
    test_dir = Path(__file__).parent.parent
    payload_file = test_dir / "fixtures" / "webhook_payload_audio.json"

    with open(payload_file, "r") as f:
        payload_data = json.load(f)

    return WhatsAppWebhookPayload(**payload_data)


@pytest.fixture
def test_audio_data():
    """Load test audio file data"""
    test_dir = Path(__file__).parent.parent
    audio_file = test_dir / "fixtures" / "test_audio.ogg"

    if not audio_file.exists():
        pytest.skip(f"Test audio file not found: {audio_file}")

    with open(audio_file, "rb") as f:
        return f.read()


class TestProcessorIntegration:
    """Integration tests for message processor"""

    @pytest.mark.asyncio
    async def test_process_text_message_no_s3_upload(self, text_payload, storage_service):
        """Test that processing a text message does not upload anything to S3"""
        # Track S3 operations
        uploaded_keys = []
        original_upload_audio = storage_service.upload_audio
        original_upload_text = storage_service.upload_text

        async def track_upload_audio(*args, **kwargs):
            result = await original_upload_audio(*args, **kwargs)
            uploaded_keys.append(result)
            return result

        async def track_upload_text(*args, **kwargs):
            result = await original_upload_text(*args, **kwargs)
            uploaded_keys.append(kwargs.get('filename', 'unknown'))
            return result

        # Mock TwilioWhatsAppClient.send_message since it's called for text messages
        with patch('voice_parser.core.processor.TwilioWhatsAppClient') as mock_whatsapp_class:
            mock_whatsapp_instance = MagicMock()
            mock_whatsapp_instance.send_message = AsyncMock()
            mock_whatsapp_class.return_value = mock_whatsapp_instance

            # Patch S3StorageService to track uploads
            with patch('voice_parser.core.processor.S3StorageService') as mock_s3_class:
                mock_s3_instance = MagicMock()
                mock_s3_instance.upload_audio = AsyncMock(side_effect=track_upload_audio)
                mock_s3_instance.upload_text = AsyncMock(side_effect=track_upload_text)
                mock_s3_class.return_value = mock_s3_instance

                # Process the text message
                result = await process_message(text_payload)

                # Verify result
                assert result["status"] == "ignored"
                assert result["reason"] == "not an audio message (type: text)"

                # Verify send_message was called with correct message
                mock_whatsapp_instance.send_message.assert_called_once()
                call_args = mock_whatsapp_instance.send_message.call_args
                assert "whatsapp:+14155552672" in call_args.kwargs["recipient_phone"]
                assert "Text messages are not supported" in call_args.kwargs["body"]

                # Verify NO S3 uploads occurred
                assert len(uploaded_keys) == 0
                mock_s3_instance.upload_audio.assert_not_called()
                mock_s3_instance.upload_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_audio_message_with_s3_uploads(
        self, audio_payload, test_audio_data, storage_service
    ):
        """Test that processing an audio message uploads to S3 and sends response"""
        # Extract media_url from payload for tracking
        media_url = audio_payload.get_media_url()
        message_id = audio_payload.MessageSid
        uploaded_keys = []

        # Track actual S3 uploads for cleanup
        try:
            # Mock TwilioWhatsAppClient
            with patch('voice_parser.core.processor.TwilioWhatsAppClient') as mock_whatsapp_class:
                mock_whatsapp_instance = MagicMock()
                mock_whatsapp_instance.download_media = AsyncMock(return_value=test_audio_data)
                mock_whatsapp_instance.send_message = AsyncMock()
                mock_whatsapp_class.return_value = mock_whatsapp_instance

                # Process the audio message
                result = await process_message(audio_payload)

                # Verify result
                assert result["status"] == "success"
                assert result["message_id"] == message_id
                assert "s3_key" in result
                assert "transcription_length" in result
                assert "analysis" in result

                uploaded_keys.append(result["s3_key"])
                uploaded_keys.append(f"{result['s3_key']}_summary.txt")

                # Verify TwilioWhatsAppClient.download_media was called with media_url
                mock_whatsapp_instance.download_media.assert_called_once_with(media_url)

                # Verify send_message was called
                assert mock_whatsapp_instance.send_message.call_count == 1
                call_args = mock_whatsapp_instance.send_message.call_args
                assert "whatsapp:+14155552671" in call_args.kwargs["recipient_phone"]
                assert "Structured text:" in call_args.kwargs["body"]

                # Verify S3 files were created
                audio_key = result["s3_key"]
                summary_key = f"{audio_key}_summary.txt"

                # Verify audio file exists in S3
                audio_data = await storage_service.download(audio_key)
                assert audio_data == test_audio_data
                assert len(audio_data) > 0

                # Verify summary text file exists in S3
                summary_data = await storage_service.download(summary_key)
                assert len(summary_data) > 0
                summary_text = summary_data.decode('utf-8')
                assert "*Summary:*" in summary_text
                assert "*Topics:*" in summary_text
                assert "*Action Items:*" in summary_text
                assert "*Sentiment:*" in summary_text

        finally:
            # Clean up: delete uploaded files from S3
            for key in uploaded_keys:
                try:
                    await storage_service.delete(key)
                except Exception as e:
                    print(f"Failed to clean up {key}: {e}")

    @pytest.mark.asyncio
    async def test_process_audio_message_response_format(
        self, audio_payload, test_audio_data, storage_service
    ):
        """Test the structured response format sent via WhatsApp"""
        uploaded_keys = []

        try:
            with patch('voice_parser.core.processor.TwilioWhatsAppClient') as mock_whatsapp_class:
                mock_whatsapp_instance = MagicMock()
                mock_whatsapp_instance.download_media = AsyncMock(return_value=test_audio_data)
                mock_whatsapp_instance.send_message = AsyncMock()
                mock_whatsapp_class.return_value = mock_whatsapp_instance

                # Process the audio message
                result = await process_message(audio_payload)

                uploaded_keys.append(result["s3_key"])
                uploaded_keys.append(f"{result['s3_key']}_summary.txt")

                # Get the message that was sent
                call_args = mock_whatsapp_instance.send_message.call_args
                sent_body = call_args.kwargs["body"]

                # Verify the structured format
                assert "Structured text:" in sent_body
                assert "*Summary:*" in sent_body
                assert "*Topics:*" in sent_body
                assert "*Action Items:*" in sent_body
                assert "*Sentiment:*" in sent_body

                # Verify analysis structure
                analysis = result["analysis"]
                assert "summary" in analysis
                assert "topics" in analysis
                assert "action_items" in analysis
                assert "sentiment" in analysis
                assert isinstance(analysis["topics"], list)
                assert isinstance(analysis["action_items"], list)

        finally:
            # Clean up
            for key in uploaded_keys:
                try:
                    await storage_service.delete(key)
                except Exception:
                    pass
