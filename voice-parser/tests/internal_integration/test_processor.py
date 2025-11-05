import pytest
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from unittest.mock import AsyncMock, patch, MagicMock
from ai_voice_shared import TwilioWebhookPayload
from voice_parser.core.processor import process_message
from ai_voice_shared.services.s3_service import S3Service
from voice_parser.services.llm.models import JobsToBeDoneDocumentModel, MessageMetadata, MessageIntent
from ai_voice_shared.settings import S3Settings
from ai_voice_shared import CustomerMetadata


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
    return S3Service(settings=test_s3_settings)


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
        """Test that processing a text message uploads text to S3 and processes it"""
        # Mock data
        mock_customer_metadata = CustomerMetadata(
            customer_id="test-customer-id",
            company_id="test-company-id",
            company_name="test-company"
        )
        mock_message_metadata = MessageMetadata(
            intent=MessageIntent.JOB_TO_BE_DONE,
            tag="test-job-summary"
        )
        mock_analysis = JobsToBeDoneDocumentModel(
            summary="Test summary",
            job="Johnson bathroom renovation",
            context="Tasks for tomorrow",
            action_items=["action1", "action2"]
        )

        # Mock CustomerLookupClient
        with patch('voice_parser.core.processor.CustomerLookupClient') as mock_customer_class:
            mock_customer_instance = MagicMock()
            mock_customer_instance.fetch_customer_metadata = AsyncMock(return_value=mock_customer_metadata)
            mock_customer_class.return_value = mock_customer_instance

            # Mock TwilioWhatsAppClient
            with patch('voice_parser.core.processor.TwilioWhatsAppClient') as mock_whatsapp_class:
                mock_whatsapp_instance = MagicMock()
                mock_whatsapp_instance.send_message = AsyncMock()
                mock_whatsapp_class.return_value = mock_whatsapp_instance

                # Mock S3Service
                with patch('voice_parser.core.processor.S3Service') as mock_s3_class:
                    mock_s3_instance = MagicMock()
                    mock_s3_instance.upload = AsyncMock(side_effect=[
                        "test-company/job-to-be-done/test-job-summary_MSG123/full_text.txt",
                        "test-company/job-to-be-done/test-job-summary_MSG123/text_summary.txt"
                    ])
                    mock_s3_class.return_value = mock_s3_instance

                    # Mock LLMClient
                    with patch('voice_parser.core.processor.LLMClient') as mock_llm_class:
                        mock_llm_instance = MagicMock()
                        mock_llm_instance.extract_message_metadata = AsyncMock(return_value=mock_message_metadata)
                        mock_llm_instance.structure_full_text = AsyncMock(return_value=mock_analysis)
                        mock_llm_class.return_value = mock_llm_instance

                        # Process the text message
                        result = await process_message(text_payload)

                        # Verify result
                        assert result["status"] == "success"
                        assert result["message_id"] == text_payload.MessageSid
                        assert "s3_keys" in result
                        assert "full_text" in result["s3_keys"]
                        assert "text_summary" in result["s3_keys"]
                        assert "metadata" in result
                        assert result["metadata"]["intent"] == "job-to-be-done"
                        assert result["metadata"]["tag"] == "test-job-summary"
                        assert result["analysis"] == mock_analysis.model_dump()

                        # Verify CustomerLookupClient was called
                        mock_customer_instance.fetch_customer_metadata.assert_called_once()

                        # Verify send_message was called TWICE (confirmation + response)
                        assert mock_whatsapp_instance.send_message.call_count == 2
                        first_call = mock_whatsapp_instance.send_message.call_args_list[0]
                        assert "Message received" in first_call.kwargs["body"]
                        second_call = mock_whatsapp_instance.send_message.call_args_list[1]
                        assert "Successfully ingested the following items:" in second_call.kwargs["body"]

                        # Verify S3 uploads occurred (full_text + text_summary)
                        assert mock_s3_instance.upload.call_count == 2

                        # Verify LLM calls
                        mock_llm_instance.extract_message_metadata.assert_called_once()
                        mock_llm_instance.structure_full_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_audio_message_with_s3_uploads(
        self, audio_payload, test_audio_data
    ):
        """Test that processing an audio message uploads to S3 and sends response"""
        # Extract media_url from payload for tracking
        media_url = audio_payload.get_media_url()
        message_id = audio_payload.MessageSid

        # Mock data
        mock_customer_metadata = CustomerMetadata(
            customer_id="test-customer-id",
            company_id="test-company-id",
            company_name="test-company"
        )
        mock_message_metadata = MessageMetadata(
            intent=MessageIntent.JOB_TO_BE_DONE,
            tag="test-job-summary"
        )
        mock_transcription = "This is a test transcription of the audio message."
        mock_analysis = JobsToBeDoneDocumentModel(
            summary="Test summary",
            job="Johnson bathroom renovation",
            context="Tasks for tomorrow",
            action_items=["action1", "action2"]
        )

        # Mock CustomerLookupClient
        with patch('voice_parser.core.processor.CustomerLookupClient') as mock_customer_class:
            mock_customer_instance = MagicMock()
            mock_customer_instance.fetch_customer_metadata = AsyncMock(return_value=mock_customer_metadata)
            mock_customer_class.return_value = mock_customer_instance

            # Mock TwilioWhatsAppClient
            with patch('voice_parser.core.processor.TwilioWhatsAppClient') as mock_whatsapp_class:
                mock_whatsapp_instance = MagicMock()
                mock_whatsapp_instance.download_media = AsyncMock(return_value=test_audio_data)
                mock_whatsapp_instance.send_message = AsyncMock()
                mock_whatsapp_class.return_value = mock_whatsapp_instance

                # Mock S3Service
                with patch('voice_parser.core.processor.S3Service') as mock_s3_class:
                    mock_s3_instance = MagicMock()
                    mock_s3_instance.upload = AsyncMock(side_effect=[
                        "test-company/job-to-be-done/test-job-summary_MSG123/audio.ogg",
                        "test-company/job-to-be-done/test-job-summary_MSG123/full_text.txt",
                        "test-company/job-to-be-done/test-job-summary_MSG123/text_summary.txt"
                    ])
                    mock_s3_class.return_value = mock_s3_instance

                    # Mock TranscriptionClient
                    with patch('voice_parser.core.processor.TranscriptionClient') as mock_transcription_class:
                        mock_transcription_instance = MagicMock()
                        mock_transcription_instance.transcribe = AsyncMock(return_value=mock_transcription)
                        mock_transcription_class.return_value = mock_transcription_instance

                        # Mock LLMClient
                        with patch('voice_parser.core.processor.LLMClient') as mock_llm_class:
                            mock_llm_instance = MagicMock()
                            mock_llm_instance.extract_message_metadata = AsyncMock(return_value=mock_message_metadata)
                            mock_llm_instance.structure_full_text = AsyncMock(return_value=mock_analysis)
                            mock_llm_class.return_value = mock_llm_instance

                            # Process the audio message
                            result = await process_message(audio_payload)

                            # Verify result
                            assert result["status"] == "success"
                            assert result["message_id"] == message_id
                            assert "s3_keys" in result
                            assert "audio" in result["s3_keys"]
                            assert "full_text" in result["s3_keys"]
                            assert "text_summary" in result["s3_keys"]
                            assert "test-company" in result["s3_keys"]["audio"]
                            assert "job-to-be-done" in result["s3_keys"]["audio"]
                            assert result["transcription_length"] == len(mock_transcription)
                            assert "metadata" in result
                            assert result["metadata"]["intent"] == "job-to-be-done"
                            assert result["metadata"]["tag"] == "test-job-summary"
                            assert result["analysis"] == mock_analysis.model_dump()

                            # Verify CustomerLookupClient was called
                            mock_customer_instance.fetch_customer_metadata.assert_called_once()

                            # Verify TwilioWhatsAppClient.download_media was called with media_url
                            mock_whatsapp_instance.download_media.assert_called_once_with(media_url)

                            # Verify S3 uploads were called (audio + full_text + text_summary)
                            assert mock_s3_instance.upload.call_count == 3

                            # Verify transcription was called with both audio_data and filename
                            mock_transcription_instance.transcribe.assert_called_once()
                            call_args = mock_transcription_instance.transcribe.call_args
                            assert call_args[0][0] == test_audio_data  # audio_data is first positional arg

                            # Verify LLM was called with correct methods
                            mock_llm_instance.extract_message_metadata.assert_called_once_with(mock_transcription)
                            mock_llm_instance.structure_full_text.assert_called_once_with(
                                mock_transcription,
                                MessageIntent.JOB_TO_BE_DONE
                            )

                            # Verify send_message was called TWICE (confirmation + response)
                            assert mock_whatsapp_instance.send_message.call_count == 2
                            first_call = mock_whatsapp_instance.send_message.call_args_list[0]
                            assert "Message received" in first_call.kwargs["body"]
                            second_call = mock_whatsapp_instance.send_message.call_args_list[1]
                            assert "whatsapp:+15551234567" in second_call.kwargs["recipient_phone"]
                            assert "Successfully ingested the following items:" in second_call.kwargs["body"]

    @pytest.mark.asyncio
    async def test_process_audio_message_response_format(
        self, audio_payload, test_audio_data
    ):
        """Test the structured response format sent via WhatsApp"""
        # Mock data
        mock_customer_metadata = CustomerMetadata(
            customer_id="test-customer-id",
            company_id="test-company-id",
            company_name="test-company"
        )
        mock_message_metadata = MessageMetadata(
            intent=MessageIntent.JOB_TO_BE_DONE,
            tag="test-job-summary"
        )
        mock_transcription = "This is a test transcription of the audio message."
        mock_analysis = JobsToBeDoneDocumentModel(
            summary="Test summary of the message",
            job="Johnson bathroom renovation",
            context="Tasks for tomorrow",
            action_items=["action1", "action2"]
        )

        # Mock CustomerLookupClient
        with patch('voice_parser.core.processor.CustomerLookupClient') as mock_customer_class:
            mock_customer_instance = MagicMock()
            mock_customer_instance.fetch_customer_metadata = AsyncMock(return_value=mock_customer_metadata)
            mock_customer_class.return_value = mock_customer_instance

            # Mock TwilioWhatsAppClient
            with patch('voice_parser.core.processor.TwilioWhatsAppClient') as mock_whatsapp_class:
                mock_whatsapp_instance = MagicMock()
                mock_whatsapp_instance.download_media = AsyncMock(return_value=test_audio_data)
                mock_whatsapp_instance.send_message = AsyncMock()
                mock_whatsapp_class.return_value = mock_whatsapp_instance

                # Mock S3Service
                with patch('voice_parser.core.processor.S3Service') as mock_s3_class:
                    mock_s3_instance = MagicMock()
                    mock_s3_instance.upload = AsyncMock(side_effect=[
                        "test-company/job-to-be-done/test-job-summary_MSG123/audio.ogg",
                        "test-company/job-to-be-done/test-job-summary_MSG123/full_text.txt",
                        "test-company/job-to-be-done/test-job-summary_MSG123/text_summary.txt"
                    ])
                    mock_s3_class.return_value = mock_s3_instance

                    # Mock TranscriptionClient
                    with patch('voice_parser.core.processor.TranscriptionClient') as mock_transcription_class:
                        mock_transcription_instance = MagicMock()
                        mock_transcription_instance.transcribe = AsyncMock(return_value=mock_transcription)
                        mock_transcription_class.return_value = mock_transcription_instance

                        # Mock LLMClient
                        with patch('voice_parser.core.processor.LLMClient') as mock_llm_class:
                            mock_llm_instance = MagicMock()
                            mock_llm_instance.extract_message_metadata = AsyncMock(return_value=mock_message_metadata)
                            mock_llm_instance.structure_full_text = AsyncMock(return_value=mock_analysis)
                            mock_llm_class.return_value = mock_llm_instance

                            # Process the audio message
                            result = await process_message(audio_payload)

                            # Verify send_message was called TWICE
                            assert mock_whatsapp_instance.send_message.call_count == 2

                            # Get the confirmation message (first call)
                            first_call = mock_whatsapp_instance.send_message.call_args_list[0]
                            assert "Message received" in first_call.kwargs["body"]

                            # Get the response message (second call)
                            second_call = mock_whatsapp_instance.send_message.call_args_list[1]
                            sent_body = second_call.kwargs["body"]

                            # Verify the structured format in the response
                            assert "Successfully ingested the following items:" in sent_body
                            assert "*Summary:*" in sent_body
                            assert "*Job:*" in sent_body
                            assert "*Context:*" in sent_body
                            assert "*Action Items:*" in sent_body

                            # Verify analysis structure in result
                            analysis = result["analysis"]
                            assert "summary" in analysis
                            assert "job" in analysis
                            assert "context" in analysis
                            assert "action_items" in analysis
                            assert isinstance(analysis["action_items"], list)
