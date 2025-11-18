"""End-to-end test for text message processing through the full pipeline."""

import pytest
import httpx
from typing import Dict, Any

from utils.twilio_signature import generate_twilio_signature, create_webhook_request_body
from utils.s3_helpers import wait_for_s3_files, download_s3_file, cleanup_s3_files


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_text_message_full_pipeline(
    e2e_config: Dict[str, Any],
    s3_client,
    http_client: httpx.AsyncClient,
    test_message_id: str
):
    """
    Test the complete flow for a text message:
    1. POST to webhook API with valid Twilio signature
    2. Wait for SQS processing and S3 upload
    3. Verify files in S3
    4. Verify content through Data API
    5. Cleanup test data
    """
    # ========== SETUP ==========
    test_company_id = e2e_config["test_company_id"]
    test_phone = e2e_config["test_phone_number"]

    # Build webhook payload (reusing structure from voice-parser fixtures)
    webhook_params = {
        "MessageSid": test_message_id,
        "SmsMessageSid": test_message_id,
        "AccountSid": e2e_config["twilio_account_sid"],
        "From": test_phone,
        "To": e2e_config["twilio_whatsapp_number"],
        "Body": "E2E Test: Install new bathroom fixtures for the Johnson renovation. Priority: high. Deadline: Friday.",
        "NumMedia": "0",
        "MessageType": "text",
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
    print(f"\n[E2E] Posting webhook for message {test_message_id}")

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
    # Expected files: full_text.txt and text_summary.txt (no audio for text messages)
    # The intent will be determined by LLM - likely "job-to-be-done" given the content
    # We'll search across all intents
    s3_prefix = f"{test_company_id}/"

    print(f"[E2E] Waiting for S3 files at prefix: {s3_prefix}")

    try:
        files = await wait_for_s3_files(
            s3_client=s3_client,
            bucket=e2e_config["s3_bucket"],
            prefix=s3_prefix,
            expected_file_patterns=[test_message_id, "_full_text.txt"],
            timeout_seconds=e2e_config["timeout_seconds"],
            poll_interval=3.0
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
    assert len(message_files) >= 2, f"Expected at least 2 files (full_text, text_summary), found {len(message_files)}"

    # Check for expected file types
    file_keys = [f.key for f in message_files]
    full_text_files = [k for k in file_keys if "_full_text.txt" in k]
    text_summary_files = [k for k in file_keys if "text_summary.txt" in k]

    assert len(full_text_files) == 1, f"Expected 1 full_text file, found {len(full_text_files)}"
    assert len(text_summary_files) == 1, f"Expected 1 text_summary file, found {len(text_summary_files)}"

    # Download and verify full_text content
    full_text_content = await download_s3_file(
        s3_client,
        e2e_config["s3_bucket"],
        full_text_files[0]
    )
    full_text = full_text_content.decode("utf-8")

    assert "Johnson renovation" in full_text, "Full text should contain message content"
    assert "bathroom fixtures" in full_text, "Full text should contain message content"
    print(f"[E2E] Full text verified ({len(full_text)} chars)")

    # Download and verify text_summary (structured by LLM)
    text_summary_content = await download_s3_file(
        s3_client,
        e2e_config["s3_bucket"],
        text_summary_files[0]
    )
    text_summary = text_summary_content.decode("utf-8")

    # The summary should have been structured by the LLM
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

    # Test presigned URL generation
    test_file_key = full_text_files[0]
    presigned_response = await http_client.get(
        f"{e2e_config['data_api_url']}/files/get-download-url",
        headers={"x-api-key": e2e_config["data_api_key"]},
        params={"key": test_file_key}
    )

    assert presigned_response.status_code == 200, f"Presigned URL generation failed: {presigned_response.status_code}"
    presigned_url = presigned_response.json()["url"]
    assert "X-Amz-Algorithm" in presigned_url, "Expected presigned URL parameters"
    print(f"[E2E] Presigned URL generated successfully")

    # Download file via presigned URL
    download_response = await http_client.get(presigned_url)
    assert download_response.status_code == 200, "Download via presigned URL failed"
    downloaded_content = download_response.text
    assert downloaded_content == full_text, "Downloaded content should match S3 content"
    print(f"[E2E] File download via presigned URL verified")

    # ========== CLEANUP ==========
    print(f"[E2E] Cleaning up test data")
    deleted_count = await cleanup_s3_files(
        s3_client,
        e2e_config["s3_bucket"],
        s3_prefix
    )
    print(f"[E2E] Deleted {deleted_count} test files")

    print(f"[E2E] ✅ Text message E2E test completed successfully")
