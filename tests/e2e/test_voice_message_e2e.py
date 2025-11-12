"""End-to-end test for voice message processing through the full pipeline."""

import pytest
import httpx
from typing import Dict, Any
import os

from utils.twilio_signature import generate_twilio_signature, create_webhook_request_body
from utils.s3_helpers import wait_for_s3_files, download_s3_file, cleanup_s3_files


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_voice_message_full_pipeline(
    e2e_config: Dict[str, Any],
    s3_client,
    http_client: httpx.AsyncClient,
    test_message_id: str
):
    """
    Test the complete flow for a voice message:
    1. Upload test audio to mock Twilio media URL (or use real Twilio if configured)
    2. POST to webhook API with valid Twilio signature
    3. Wait for SQS processing, transcription, and S3 upload
    4. Verify files in S3 (audio, full_text, text_summary)
    5. Verify content through Data API
    6. Cleanup test data

    Note: This test requires the voice-parser Lambda to download from a real Twilio URL.
    In a real scenario, you'd need to either:
    - Use Twilio's test mode to upload real media
    - Mock the Twilio media endpoint
    - Use a publicly accessible URL for test audio

    For this implementation, we'll simulate the webhook but note that actual voice
    processing requires real Twilio media URLs.
    """
    # ========== SETUP ==========
    test_company_id = e2e_config["test_company_id"]
    test_phone = e2e_config["test_phone_number"]

    # Check if test audio exists
    test_audio_path = os.path.join(os.path.dirname(__file__), "fixtures", "test_audio.ogg")
    if not os.path.exists(test_audio_path):
        pytest.skip(f"Test audio file not found: {test_audio_path}")

    # NOTE: For a true E2E test with voice messages, you need a real Twilio MediaUrl
    # that the Lambda can download from. This is a limitation of testing voice messages.
    # Options:
    # 1. Use Twilio's API to upload media and get a real URL
    # 2. Host test audio on a public URL
    # 3. Mock the Twilio download endpoint
    #
    # For this example, we'll skip if no real media URL is configured
    real_media_url = os.getenv("E2E_TEST_AUDIO_MEDIA_URL")
    if not real_media_url:
        pytest.skip(
            "Voice message E2E test requires E2E_TEST_AUDIO_MEDIA_URL to be set. "
            "This should be a publicly accessible URL (e.g., from Twilio) that the "
            "Lambda can download the test audio from."
        )

    # Build webhook payload for voice message
    webhook_params = {
        "MessageSid": test_message_id,
        "SmsMessageSid": test_message_id,
        "AccountSid": e2e_config["twilio_account_sid"],
        "From": test_phone,
        "To": e2e_config["twilio_whatsapp_number"],
        "Body": "",  # Empty for voice messages
        "NumMedia": "1",
        "MediaContentType0": "audio/ogg",
        "MediaUrl0": real_media_url,
        "MessageType": "audio",
        "SmsStatus": "received",
        "NumSegments": "1",
        "ApiVersion": "2010-04-01",
        "ProfileName": "E2E Test User",
        "WaId": test_phone.replace("whatsapp:+", ""),
    }

    # Generate valid Twilio signature
    webhook_url = e2e_config["webhook_url"]
    signature = generate_twilio_signature(
        webhook_url,
        webhook_params,
        e2e_config["twilio_auth_token"]
    )

    # ========== ACT: POST to Webhook ==========
    print(f"\n[E2E] Posting voice webhook for message {test_message_id}")

    response = await http_client.post(
        webhook_url,
        headers={
            "X-Twilio-Signature": signature,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        content=create_webhook_request_body(webhook_params),
    )

    # Verify webhook accepted the request
    assert response.status_code == 200, f"Webhook failed: {response.status_code} - {response.text}"
    print(f"[E2E] Webhook accepted with status 200")

    # ========== WAIT: Poll S3 for Processing ==========
    # Expected files: audio.ogg, full_text.txt (transcription), text_summary.txt
    s3_prefix = f"{test_company_id}/"

    print(f"[E2E] Waiting for S3 files at prefix: {s3_prefix}")
    print(f"[E2E] This may take longer as it involves audio transcription...")

    try:
        files = await wait_for_s3_files(
            s3_client=s3_client,
            bucket=e2e_config["s3_bucket"],
            prefix=s3_prefix,
            expected_file_patterns=[
                test_message_id,
                "_audio.ogg",
                "_full_text.txt"
            ],
            timeout_seconds=e2e_config["timeout_seconds"],
            poll_interval=5.0  # Longer interval for voice processing
        )

        print(f"[E2E] Found {len(files)} files in S3:")
        for f in files:
            print(f"  - {f.key} ({f.size} bytes)")

    except TimeoutError as e:
        # Cleanup and fail
        if e2e_config["cleanup_on_failure"]:
            await cleanup_s3_files(s3_client, e2e_config["s3_bucket"], s3_prefix)
        pytest.fail(str(e))

    # ========== VERIFY: Check S3 Files ==========
    # Find files for this message
    message_files = [f for f in files if test_message_id in f.key]
    assert len(message_files) >= 3, f"Expected at least 3 files (audio, full_text, text_summary), found {len(message_files)}"

    # Check for expected file types
    file_keys = [f.key for f in message_files]
    audio_files = [k for k in file_keys if "_audio.ogg" in k]
    full_text_files = [k for k in file_keys if "_full_text.txt" in k]
    text_summary_files = [k for k in file_keys if "_text_summary.txt" in k]

    assert len(audio_files) == 1, f"Expected 1 audio file, found {len(audio_files)}"
    assert len(full_text_files) == 1, f"Expected 1 full_text file, found {len(full_text_files)}"
    assert len(text_summary_files) == 1, f"Expected 1 text_summary file, found {len(text_summary_files)}"

    # Verify audio file was stored
    audio_size = next(f.size for f in message_files if "_audio.ogg" in f.key)
    assert audio_size > 0, "Audio file should not be empty"
    print(f"[E2E] Audio file verified ({audio_size} bytes)")

    # Download and verify transcription
    full_text_content = await download_s3_file(
        s3_client,
        e2e_config["s3_bucket"],
        full_text_files[0]
    )
    transcription = full_text_content.decode("utf-8")

    assert len(transcription) > 0, "Transcription should not be empty"
    print(f"[E2E] Transcription verified ({len(transcription)} chars)")
    print(f"[E2E] Transcription: {transcription[:200]}...")

    # Download and verify text_summary (structured by LLM)
    text_summary_content = await download_s3_file(
        s3_client,
        e2e_config["s3_bucket"],
        text_summary_files[0]
    )
    text_summary = text_summary_content.decode("utf-8")

    assert len(text_summary) > 0, "Text summary should not be empty"
    print(f"[E2E] Text summary verified ({len(text_summary)} chars)")
    print(f"[E2E] Summary preview: {text_summary[:200]}...")

    # Determine intent from file path
    intent = None
    for f in message_files:
        if "job-to-be-done" in f.key:
            intent = "job-to-be-done"
        elif "knowledge-document" in f.key:
            intent = "knowledge-document"
        elif "other" in f.key:
            intent = "other"

    assert intent is not None, "Could not determine message intent from S3 keys"
    print(f"[E2E] Message classified as intent: {intent}")

    # ========== VERIFY: Data API Access ==========
    print(f"[E2E] Verifying Data API can list the files")

    data_api_response = await http_client.get(
        f"{e2e_config['data_api_url']}/files/list",
        headers={"x-api-key": e2e_config["data_api_key"]},
        params={
            "company_id": test_company_id,
            "message_intent": intent,
        }
    )

    assert data_api_response.status_code == 200, f"Data API failed: {data_api_response.status_code}"

    data_api_files = data_api_response.json()["files"]
    api_file_keys = [f["key"] for f in data_api_files]

    # Verify our test message files are in the API response
    assert any(test_message_id in k for k in api_file_keys), "Test message files not found in Data API response"
    print(f"[E2E] Data API returned {len(data_api_files)} files, including our test message")

    # Test presigned URL generation for audio file
    test_audio_key = audio_files[0]
    presigned_response = await http_client.get(
        f"{e2e_config['data_api_url']}/files/get-download-url",
        headers={"x-api-key": e2e_config["data_api_key"]},
        params={"key": test_audio_key}
    )

    assert presigned_response.status_code == 200, f"Presigned URL generation failed: {presigned_response.status_code}"
    presigned_url = presigned_response.json()["url"]
    assert "X-Amz-Algorithm" in presigned_url, "Expected presigned URL parameters"
    print(f"[E2E] Presigned URL for audio generated successfully")

    # Download audio via presigned URL
    download_response = await http_client.get(presigned_url)
    assert download_response.status_code == 200, "Download via presigned URL failed"
    assert len(download_response.content) == audio_size, "Downloaded audio size should match S3"
    print(f"[E2E] Audio file download via presigned URL verified")

    # ========== CLEANUP ==========
    print(f"[E2E] Cleaning up test data")
    deleted_count = await cleanup_s3_files(
        s3_client,
        e2e_config["s3_bucket"],
        s3_prefix
    )
    print(f"[E2E] Deleted {deleted_count} test files")

    print(f"[E2E] ✅ Voice message E2E test completed successfully")
