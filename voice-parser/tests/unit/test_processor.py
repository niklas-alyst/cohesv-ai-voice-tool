import pytest
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from unittest.mock import AsyncMock, patch, MagicMock
from voice_parser.models import TwilioWebhookPayload
from voice_parser.core.processor import process_message
from voice_parser.services.storage import S3StorageService
from voice_parser.services.llm import VoiceNoteAnalysis
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

    return TwilioWebhookPayload(**payload_data)


@pytest.fixture
def audio_payload():
    """Load audio message webhook payload"""
    test_dir = Path(__file__).parent.parent
    payload_file = test_dir / "fixtures" / "webhook_payload_audio.json"

    with open(payload_file, "r") as f:
        payload_data = json.load(f)

    return TwilioWebhookPayload(**payload_data)


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
    async def test_process_text_message_no_s3_upload(self, text_payload):
        """Test that processing a text message does not upload anything to S3"""
        # Mock TwilioWhatsAppClient.send_message since it's called for text messages
        with patch('voice_parser.core.processor.TwilioWhatsAppClient') as mock_whatsapp_class:
            mock_whatsapp_instance = MagicMock()
            mock_whatsapp_instance.send_message = AsyncMock()
            mock_whatsapp_class.return_value = mock_whatsapp_instance

            # Patch S3StorageService to track uploads (without actually uploading)
            with patch('voice_parser.core.processor.S3StorageService') as mock_s3_class:
                mock_s3_instance = MagicMock()
                mock_s3_instance.upload_audio = AsyncMock()
                mock_s3_instance.upload_text = AsyncMock()
                mock_s3_instance.download = AsyncMock(return_value=b'')
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
                mock_s3_instance.upload_audio.assert_not_called()
                mock_s3_instance.upload_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_audio_message_with_s3_uploads(
        self, audio_payload, test_audio_data
    ):
        """Test that processing an audio message uploads to S3 and sends response"""
        # Extract media_url from payload for tracking
        media_url = audio_payload.get_media_url()
        message_id = audio_payload.MessageSid

        # Mock transcription and analysis
        mock_transcription = "This is a test transcription of the audio message."
        mock_analysis = VoiceNoteAnalysis(
            summary="Test summary",
            topics=["topic1", "topic2"],
            action_items=["action1", "action2"],
            sentiment="neutral"
        )

        # Mock TwilioWhatsAppClient
        with patch('voice_parser.core.processor.TwilioWhatsAppClient') as mock_whatsapp_class:
            mock_whatsapp_instance = MagicMock()
            mock_whatsapp_instance.download_media = AsyncMock(return_value=test_audio_data)
            mock_whatsapp_instance.send_message = AsyncMock()
            mock_whatsapp_class.return_value = mock_whatsapp_instance

            # Mock S3StorageService
            with patch('voice_parser.core.processor.S3StorageService') as mock_s3_class:
                mock_s3_instance = MagicMock()
                mock_s3_instance.upload_audio = AsyncMock(return_value="test/audio/key.ogg")
                mock_s3_instance.upload_text = AsyncMock()
                mock_s3_instance.download = AsyncMock(return_value=test_audio_data)
                mock_s3_class.return_value = mock_s3_instance

                # Mock TranscriptionClient
                with patch('voice_parser.core.processor.TranscriptionClient') as mock_transcription_class:
                    mock_transcription_instance = MagicMock()
                    mock_transcription_instance.transcribe = AsyncMock(return_value=mock_transcription)
                    mock_transcription_class.return_value = mock_transcription_instance

                    # Mock LLMClient
                    with patch('voice_parser.core.processor.LLMClient') as mock_llm_class:
                        mock_llm_instance = MagicMock()
                        mock_llm_instance.structure_text = AsyncMock(return_value=mock_analysis)
                        mock_llm_class.return_value = mock_llm_instance

                        # Process the audio message
                        result = await process_message(audio_payload)

                        # Verify result
                        assert result["status"] == "success"
                        assert result["message_id"] == message_id
                        assert result["s3_key"] == "test/audio/key.ogg"
                        assert result["transcription_length"] == len(mock_transcription)
                        assert result["analysis"] == mock_analysis.model_dump()

                        # Verify TwilioWhatsAppClient.download_media was called with media_url
                        mock_whatsapp_instance.download_media.assert_called_once_with(media_url)

                        # Verify S3 uploads were called
                        mock_s3_instance.upload_audio.assert_called_once()
                        mock_s3_instance.upload_text.assert_called_once()

                        # Verify transcription was called with both audio_data and filename
                        mock_transcription_instance.transcribe.assert_called_once()
                        call_args = mock_transcription_instance.transcribe.call_args
                        assert call_args[0][0] == test_audio_data  # audio_data is first positional arg

                        # Verify LLM was called with structure_text (not structure_transcription)
                        mock_llm_instance.structure_text.assert_called_once_with(mock_transcription)

                        # Verify send_message was called
                        assert mock_whatsapp_instance.send_message.call_count == 1
                        call_args = mock_whatsapp_instance.send_message.call_args
                        assert "whatsapp:+15551234567" in call_args.kwargs["recipient_phone"]
                        assert "Structured text:" in call_args.kwargs["body"]

    @pytest.mark.asyncio
    async def test_process_audio_message_response_format(
        self, audio_payload, test_audio_data
    ):
        """Test the structured response format sent via WhatsApp"""
        # Mock transcription and analysis
        mock_transcription = "This is a test transcription of the audio message."
        mock_analysis = VoiceNoteAnalysis(
            summary="Test summary of the message",
            topics=["topic1", "topic2", "topic3"],
            action_items=["action1", "action2"],
            sentiment="positive"
        )

        with patch('voice_parser.core.processor.TwilioWhatsAppClient') as mock_whatsapp_class:
            mock_whatsapp_instance = MagicMock()
            mock_whatsapp_instance.download_media = AsyncMock(return_value=test_audio_data)
            mock_whatsapp_instance.send_message = AsyncMock()
            mock_whatsapp_class.return_value = mock_whatsapp_instance

            # Mock S3StorageService
            with patch('voice_parser.core.processor.S3StorageService') as mock_s3_class:
                mock_s3_instance = MagicMock()
                mock_s3_instance.upload_audio = AsyncMock(return_value="test/audio/key.ogg")
                mock_s3_instance.upload_text = AsyncMock()
                mock_s3_instance.download = AsyncMock(return_value=test_audio_data)
                mock_s3_class.return_value = mock_s3_instance

                # Mock TranscriptionClient
                with patch('voice_parser.core.processor.TranscriptionClient') as mock_transcription_class:
                    mock_transcription_instance = MagicMock()
                    mock_transcription_instance.transcribe = AsyncMock(return_value=mock_transcription)
                    mock_transcription_class.return_value = mock_transcription_instance

                    # Mock LLMClient
                    with patch('voice_parser.core.processor.LLMClient') as mock_llm_class:
                        mock_llm_instance = MagicMock()
                        mock_llm_instance.structure_text = AsyncMock(return_value=mock_analysis)
                        mock_llm_class.return_value = mock_llm_instance

                        # Process the audio message
                        result = await process_message(audio_payload)

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
