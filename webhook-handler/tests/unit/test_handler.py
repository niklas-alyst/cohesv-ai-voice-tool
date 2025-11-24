"""Unit tests for the webhook handler."""

import os
import json
import pytest
from urllib.parse import urlencode
from unittest.mock import AsyncMock
from twilio.request_validator import RequestValidator

# The handler function to be tested
from webhook_handler.handler import lambda_handler
from ai_voice_shared import TwilioWebhookPayload


@pytest.fixture
def twilio_auth_token() -> str:
    """A fake Twilio auth token."""
    return "test-twilio-auth-token"


@pytest.fixture
def validator(twilio_auth_token: str) -> RequestValidator:
    """A RequestValidator instance with the fake token."""
    return RequestValidator(twilio_auth_token)


@pytest.fixture
def base_event_params() -> dict:
    """Base parameters for a valid Twilio request."""
    return {
        'SmsMessageSid': 'SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
        'NumMedia': '0',
        'SmsSid': 'SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
        'SmsStatus': 'received',
        'Body': 'Hello',
        'To': 'whatsapp:+14155238886',
        'NumSegments': '1',
        'MessageSid': 'SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
        'AccountSid': 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
        'From': 'whatsapp:+1234567890',
        'ApiVersion': '2010-04-01',
    }


@pytest.fixture
def api_gateway_event(validator: RequestValidator, base_event_params: dict) -> dict:
    """A fixture to generate a valid API Gateway event for the Lambda handler."""
    url = "https://test-api-gw.amazonaws.com/prod/webhook"
    signature = validator.compute_signature(url, base_event_params)

    return {
        "requestContext": {
            "domainName": "test-api-gw.amazonaws.com",
            "path": "/prod/webhook",
        },
        "headers": {
            "X-Twilio-Signature": signature,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        "body": urlencode(base_event_params),
        "queryStringParameters": None,
    }


def test_handler_successful_processing(mocker, api_gateway_event, twilio_auth_token, base_event_params):
    """Test the happy path where the handler successfully processes the event."""
    mocker.patch.dict(os.environ, {
        "TWILIO_AUTH_TOKEN": twilio_auth_token,
        "SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/12345/test-queue",
        "AWS_REGION": "us-east-1",
    })

    mock_sqs_client = mocker.MagicMock()
    mocker.patch("webhook_handler.handler.boto3.client", return_value=mock_sqs_client)

    # Mock customer lookup to succeed
    mock_customer_client = mocker.MagicMock()
    mock_customer_client.fetch_customer_metadata = AsyncMock(return_value=mocker.MagicMock())
    mocker.patch("webhook_handler.handler.CustomerLookupClient", return_value=mock_customer_client)

    response = lambda_handler(api_gateway_event, None)

    assert response["statusCode"] == 200
    assert response["body"] == ""  # Twilio expects empty body for success

    # Verify SQS was called correctly
    mock_sqs_client.send_message.assert_called_once()
    sent_message_body = json.loads(mock_sqs_client.send_message.call_args.kwargs["MessageBody"])
    
    # The body sent to SQS is a JSON dump of the Pydantic model
    validated_payload = TwilioWebhookPayload(**base_event_params)
    assert sent_message_body == json.loads(validated_payload.model_dump_json())


def test_handler_returns_401_for_unauthorized_sender(mocker, api_gateway_event, twilio_auth_token, base_event_params):
    """Test that the handler returns 401 if the customer is not authorized."""
    mocker.patch.dict(os.environ, {
        "TWILIO_AUTH_TOKEN": twilio_auth_token,
        "SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/12345/test-queue",
        "AWS_REGION": "us-east-1",
    })

    # Mock customer lookup to fail
    mock_customer_client = mocker.MagicMock()
    mock_customer_client.fetch_customer_metadata = AsyncMock(side_effect=Exception("Not Found"))
    mocker.patch("webhook_handler.handler.CustomerLookupClient", return_value=mock_customer_client)

    mock_sqs_client = mocker.MagicMock()
    mocker.patch("webhook_handler.handler.boto3.client", return_value=mock_sqs_client)

    response = lambda_handler(api_gateway_event, None)

    assert response["statusCode"] == 401
    expected_error = f"Phone number not authorized: {base_event_params['From']}"
    assert json.loads(response["body"])["error"] == expected_error
    mock_sqs_client.send_message.assert_not_called()


def test_handler_returns_500_on_sqs_failure(mocker, api_gateway_event, twilio_auth_token):
    """Test that the handler returns 500 if sending to SQS fails."""
    mocker.patch.dict(os.environ, {
        "TWILIO_AUTH_TOKEN": twilio_auth_token,
        "SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/12345/test-queue",
        "AWS_REGION": "us-east-1",
    })

    mock_sqs_client = mocker.MagicMock()
    mock_sqs_client.send_message.side_effect = Exception("SQS is down")
    mocker.patch("webhook_handler.handler.boto3.client", return_value=mock_sqs_client)

    # Mock customer lookup to succeed so we can reach the SQS step
    mock_customer_client = mocker.MagicMock()
    mock_customer_client.fetch_customer_metadata = AsyncMock(return_value=mocker.MagicMock())
    mocker.patch("webhook_handler.handler.CustomerLookupClient", return_value=mock_customer_client)

    response = lambda_handler(api_gateway_event, None)

    assert response["statusCode"] == 500
    assert json.loads(response["body"])["error"] == "Failed to process webhook"


def test_handler_returns_403_on_invalid_twilio_signature(mocker, api_gateway_event, twilio_auth_token, base_event_params):
    """Test that the handler returns 403 if the Twilio signature is invalid."""
    mocker.patch.dict(os.environ, {
        "TWILIO_AUTH_TOKEN": twilio_auth_token,
        "SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/12345/test-queue",
        "AWS_REGION": "us-east-1",
    })

    # Mock customer lookup to succeed so we can reach the signature validation step
    mock_customer_client = mocker.MagicMock()
    mock_customer_client.fetch_customer_metadata = AsyncMock(return_value=mocker.MagicMock())
    mocker.patch("webhook_handler.handler.CustomerLookupClient", return_value=mock_customer_client)

    # Create an event with an invalid signature
    invalid_signature_event = api_gateway_event.copy()
    invalid_signature_event["headers"]["X-Twilio-Signature"] = "invalid-signature"

    mock_sqs_client = mocker.MagicMock()
    mocker.patch("webhook_handler.handler.boto3.client", return_value=mock_sqs_client)

    response = lambda_handler(invalid_signature_event, None)

    assert response["statusCode"] == 403
    assert json.loads(response["body"])["error"] == "Invalid Twilio signature"
    mock_sqs_client.send_message.assert_not_called()


def test_handler_returns_500_on_customer_client_init_failure(mocker, api_gateway_event, twilio_auth_token):
    """Test that the handler returns 500 if the CustomerLookupClient fails to initialize."""
    mocker.patch.dict(os.environ, {
        "TWILIO_AUTH_TOKEN": twilio_auth_token,
        "SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/12345/test-queue",
        "AWS_REGION": "us-east-1",
    })

    mocker.patch("webhook_handler.handler.boto3.client", return_value=mocker.MagicMock())
    mocker.patch("webhook_handler.handler.CustomerLookupClient", side_effect=Exception("Failed to init"))

    response = lambda_handler(api_gateway_event, None)

    assert response["statusCode"] == 500
    assert "Failed to initialize customer lookup service" in json.loads(response["body"])["error"]


def test_handler_returns_400_on_incomplete_payload(mocker, validator, twilio_auth_token):
    """Test that the handler returns 400 if the payload is missing a required field."""
    mocker.patch.dict(os.environ, {
        "TWILIO_AUTH_TOKEN": twilio_auth_token,
        "SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/12345/test-queue",
        "AWS_REGION": "us-east-1",
    })

    # Payload missing 'MessageSid'
    incomplete_params = {'From': 'whatsapp:+1234567890', 'Body': 'test'}
    url = "https://test-api-gw.amazonaws.com/prod/webhook"
    signature = validator.compute_signature(url, incomplete_params)

    event = {
        "requestContext": {"domainName": "test-api-gw.amazonaws.com", "path": "/prod/webhook"},
        "headers": {"X-Twilio-Signature": signature, "Content-Type": "application/x-www-form-urlencoded"},
        "body": urlencode(incomplete_params),
        "queryStringParameters": None,
    }

    mocker.patch("webhook_handler.handler.boto3.client", return_value=mocker.MagicMock())
    # Mock customer lookup to succeed, as it's checked before payload validation
    mock_customer_client = mocker.MagicMock()
    mock_customer_client.fetch_customer_metadata = AsyncMock(return_value=mocker.MagicMock())
    mocker.patch("webhook_handler.handler.CustomerLookupClient", return_value=mock_customer_client)

    response = lambda_handler(event, None)

    assert response["statusCode"] == 400
    assert "Invalid webhook payload structure" in json.loads(response["body"])["error"]


def test_handler_returns_500_on_missing_sqs_url_config(mocker, api_gateway_event, twilio_auth_token):
    """Test that the handler returns 500 if SQS_QUEUE_URL is not configured."""
    mocker.patch.dict(os.environ, {
        "TWILIO_AUTH_TOKEN": twilio_auth_token,
        "AWS_REGION": "us-east-1",
    }, clear=True)

    response = lambda_handler(api_gateway_event, None)

    assert response["statusCode"] == 500
    assert json.loads(response["body"])["error"] == "SQS_QUEUE_URL not configured"


def test_handler_returns_500_on_missing_twilio_token_config(mocker, api_gateway_event):
    """Test that the handler returns 500 if TWILIO_AUTH_TOKEN is not configured."""
    mocker.patch.dict(os.environ, {}, clear=True)

    response = lambda_handler(api_gateway_event, None)

    assert response["statusCode"] == 500
    assert json.loads(response["body"])["error"] == "TWILIO_AUTH_TOKEN not configured"
