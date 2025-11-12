import pytest
from ai_voice_shared.models import TwilioWebhookPayload, CustomerMetadata, S3ObjectMetadata, S3ListResponse

@pytest.fixture
def sample_text_webhook_payload():
    return {
        "MessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx1",
        "SmsSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx1",
        "SmsMessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx1",
        "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx1",
        "From": "whatsapp:+1234567890",
        "To": "whatsapp:+1098765432",
        "ProfileName": "TestUser",
        "WaId": "1234567890",
        "Body": "Hello, world!",
        "NumMedia": "0",
        "ApiVersion": "2010-04-01",
        "SmsStatus": "received",
        "MessageType": "text",
    }

@pytest.fixture
def sample_audio_webhook_payload():
    return {
        "MessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx2",
        "SmsSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx2",
        "SmsMessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx2",
        "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx2",
        "From": "whatsapp:+1234567891",
        "To": "whatsapp:+1098765431",
        "ProfileName": "AudioUser",
        "WaId": "1234567891",
        "NumMedia": "1",
        "MediaContentType0": "audio/ogg",
        "MediaUrl0": "https://api.twilio.com/2010-04-01/Accounts/ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx2/Messages/SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx2/Media/MExxxxxxxxxxxxxxxxxxxxxxxxxxxxx2",
        "ApiVersion": "2010-04-01",
        "SmsStatus": "received",
        "MessageType": "audio",
    }

@pytest.fixture
def sample_image_webhook_payload():
    return {
        "MessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx3",
        "SmsSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx3",
        "SmsMessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx3",
        "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx3",
        "From": "whatsapp:+1234567892",
        "To": "whatsapp:+1098765432",
        "ProfileName": "ImageUser",
        "WaId": "1234567892",
        "NumMedia": "1",
        "MediaContentType0": "image/jpeg",
        "MediaUrl0": "https://api.twilio.com/2010-04-01/Accounts/ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx3/Messages/SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx3/Media/MExxxxxxxxxxxxxxxxxxxxxxxxxxxxx3",
        "ApiVersion": "2010-04-01",
        "SmsStatus": "received",
        "MessageType": "image",
    }

@pytest.fixture
def sample_document_webhook_payload():
    return {
        "MessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx4",
        "SmsSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx4",
        "SmsMessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx4",
        "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx4",
        "From": "whatsapp:+1234567893",
        "To": "whatsapp:+1098765432",
        "ProfileName": "DocumentUser",
        "WaId": "1234567893",
        "NumMedia": "1",
        "MediaContentType0": "application/pdf",
        "MediaUrl0": "https://api.twilio.com/2010-04-01/Accounts/ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx4/Messages/SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx4/Media/MExxxxxxxxxxxxxxxxxxxxxxxxxxxxx4",
        "ApiVersion": "2010-04-01",
        "SmsStatus": "received",
        "MessageType": "document",
    }

@pytest.fixture
def sample_unknown_webhook_payload():
    return {
        "MessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx5",
        "SmsSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx5",
        "SmsMessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx5",
        "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx5",
        "From": "whatsapp:+1234567894",
        "To": "whatsapp:+1098765432",
        "ProfileName": "UnknownUser",
        "WaId": "1234567894",
        "NumMedia": "1",
        "MediaContentType0": "application/octet-stream",
        "MediaUrl0": "https://api.twilio.com/2010-04-01/Accounts/ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx5/Messages/SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx5/Media/MExxxxxxxxxxxxxxxxxxxxxxxxxxxxx5",
        "ApiVersion": "2010-04-01",
        "SmsStatus": "received",
        "MessageType": "unknown_type", # A type not explicitly handled
    }

def test_twilio_webhook_payload_text_message(sample_text_webhook_payload):
    payload = TwilioWebhookPayload(**sample_text_webhook_payload)
    assert payload.MessageSid == "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx1"
    assert payload.From == "whatsapp:+1234567890"
    assert payload.Body == "Hello, world!"
    assert payload.NumMedia == "0"
    assert payload.get_message_type() == "text"
    assert payload.get_media_url() is None
    assert payload.get_phone_number() == "whatsapp:+1234567890"
    assert payload.get_phone_number_without_prefix() == "1234567890"

def test_twilio_webhook_payload_audio_message(sample_audio_webhook_payload):
    payload = TwilioWebhookPayload(**sample_audio_webhook_payload)
    assert payload.MessageSid == "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx2"
    assert payload.From == "whatsapp:+1234567891"
    assert payload.Body is None
    assert payload.NumMedia == "1"
    assert payload.MediaContentType0 == "audio/ogg"
    assert payload.get_message_type() == "audio"
    assert payload.get_media_url() == "https://api.twilio.com/2010-04-01/Accounts/ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx2/Messages/SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx2/Media/MExxxxxxxxxxxxxxxxxxxxxxxxxxxxx2"

def test_twilio_webhook_payload_image_message(sample_image_webhook_payload):
    payload = TwilioWebhookPayload(**sample_image_webhook_payload)
    assert payload.get_message_type() == "image"

def test_twilio_webhook_payload_document_message(sample_document_webhook_payload):
    payload = TwilioWebhookPayload(**sample_document_webhook_payload)
    assert payload.get_message_type() == "document"

def test_twilio_webhook_payload_unknown_message_type(sample_unknown_webhook_payload):
    payload = TwilioWebhookPayload(**sample_unknown_webhook_payload)
    assert payload.get_message_type() == "document"

def test_twilio_webhook_payload_file_message_type_fallback():
    # Test case where MessageType is 'file' but content type is document
    payload_data = {
        "MessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx6",
        "SmsSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx6",
        "SmsMessageSid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx6",
        "AccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx6",
        "From": "whatsapp:+1234567895",
        "To": "whatsapp:+1098765432",
        "ProfileName": "FileUser",
        "WaId": "1234567895",
        "NumMedia": "1",
        "MediaContentType0": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "MediaUrl0": "https://example.com/file.xlsx",
        "ApiVersion": "2010-04-01",
        "SmsStatus": "received",
        "MessageType": "file", # Twilio might send 'file' for documents
    }
    payload = TwilioWebhookPayload(**payload_data)
    assert payload.get_message_type() == "document"

def test_customer_metadata_model():
    metadata = CustomerMetadata(
        customer_id="cust123", company_id="comp456", company_name="TestCo"
    )
    assert metadata.customer_id == "cust123"
    assert metadata.company_id == "comp456"
    assert metadata.company_name == "TestCo"

def test_s3_object_metadata_model():
    obj_meta = S3ObjectMetadata(
        key="path/to/file.txt",
        etag="\"abcdef12345\"",
        size=1024,
        last_modified="2023-01-01T12:00:00Z",
    )
    assert obj_meta.key == "path/to/file.txt"
    assert obj_meta.size == 1024

def test_s3_list_response_model():
    obj_meta1 = S3ObjectMetadata(
        key="path/to/file1.txt", etag="\"a\"", size=100, last_modified="2023-01-01T12:00:00Z"
    )
    obj_meta2 = S3ObjectMetadata(
        key="path/to/file2.txt", etag="\"b\"", size=200, last_modified="2023-01-01T12:01:00Z"
    )
    s3_list = S3ListResponse(files=[obj_meta1, obj_meta2], nextContinuationToken="token123")
    assert len(s3_list.files) == 2
    assert s3_list.files[0].key == "path/to/file1.txt"
    assert s3_list.nextContinuationToken == "token123"

    s3_list_no_token = S3ListResponse(files=[obj_meta1])
    assert s3_list_no_token.nextContinuationToken is None
