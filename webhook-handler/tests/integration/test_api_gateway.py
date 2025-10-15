"""Integration tests for AWS Lambda functions behind API Gateway."""

import pytest
import os
from urllib.parse import urlencode
from dotenv import load_dotenv
import httpx
from twilio.request_validator import RequestValidator


@pytest.fixture(scope="session", autouse=True)
def load_test_env():
    """Load test environment variables from .env.test"""
    load_dotenv(".env.test")


@pytest.fixture
def api_gateway_url():
    """Get API Gateway URL from environment"""
    url = os.getenv("AWS_API_GATEWAY_URL")
    if not url:
        pytest.skip("AWS_API_GATEWAY_URL not configured in .env.test")
    return url.rstrip("/")


@pytest.fixture
def twilio_auth_token():
    """Get Twilio auth token from environment"""
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not token:
        pytest.skip("TWILIO_AUTH_TOKEN not configured in .env.test")
    return token

@pytest.fixture
def sender_number():
    """Get Twilio auth token from environment"""
    token = os.getenv("SENDER_NUMBER")
    if not token:
        pytest.skip("SENDER_NUMBER not configured in .env.test")
    return token

@pytest.fixture
def validator(twilio_auth_token: str) -> RequestValidator:
    """Fixture for the Twilio request validator."""
    return RequestValidator(twilio_auth_token)


class TestTwilioWebhookHandler:
    """Integration tests for Twilio webhook handler (POST)"""

    def test_successful_event_notification(self, api_gateway_url: str, sender_number: str, validator: RequestValidator):
        """Test successful processing of a valid Twilio notification"""
        # The URL that Twilio would have requested
        url = api_gateway_url

        # The POST parameters
        params = {
            'SmsMessageSid': 'SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'NumMedia': '0',
            'SmsSid': 'SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'SmsStatus': 'received',
            'Body': 'Hello',
            'To': 'whatsapp:+14155238886',
            'NumSegments': '1',
            'MessageSid': 'SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'AccountSid': 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'From': sender_number,
            'ApiVersion': '2010-04-01',
        }

        # Generate a valid signature
        signature = validator.compute_signature(url, params)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Twilio-Signature": signature
        }

        # The body should be a URL-encoded string
        content = urlencode(params)

        response = httpx.post(
            url,
            headers=headers,
            content=content
        )

        assert response.status_code == 200, f"Got message {response.text}"
        assert response.json().get("status") == "received"

    def test_invalid_number(self, api_gateway_url: str, validator: RequestValidator):
        """Test successful processing of a valid Twilio notification"""
        # The URL that Twilio would have requested
        url = api_gateway_url

        # The POST parameters
        params = {
            'SmsMessageSid': 'SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'NumMedia': '0',
            'SmsSid': 'SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'SmsStatus': 'received',
            'Body': 'Hello',
            'To': 'whatsapp:+14155238886',
            'NumSegments': '1',
            'MessageSid': 'SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'AccountSid': 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'From': "whatsapp:+14155238912",
            'ApiVersion': '2010-04-01',
        }

        # Generate a valid signature
        signature = validator.compute_signature(url, params)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Twilio-Signature": signature
        }

        # The body should be a URL-encoded string
        content = urlencode(params)

        response = httpx.post(
            url,
            headers=headers,
            content=content
        )

        assert response.status_code == 401, f"Got message {response.text}"


    def test_invalid_signature(self, api_gateway_url: str, sender_number: str):
        """Test event notification fails with invalid signature"""
        params = {
            'From': sender_number,
            'Body': 'test'
        }
        content = urlencode(params)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Twilio-Signature": "invalid_signature_here"
        }

        response = httpx.post(
            api_gateway_url,
            headers=headers,
            content=content
        )

        assert response.status_code == 403, f"Got message {response.text}"
        assert "error" in response.json()
        assert response.json()["error"] == "Invalid Twilio signature"

    def test_missing_signature_header(self, api_gateway_url: str, sender_number: str):
        """Test event notification fails without signature header"""
        params = {
            'From': sender_number,
            'Body': 'test'
        }
        content = urlencode(params)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        response = httpx.post(
            api_gateway_url,
            headers=headers,
            content=content
        )

        assert response.status_code == 401, f"Got message {response.text}"
        assert "error" in response.json()
        assert response.json()["error"] == "Missing X-Twilio-Signature header"

    def test_missing_body(self, api_gateway_url: str, validator: RequestValidator):
        """Test event notification fails with missing body"""
        url = api_gateway_url
        params = {}  # No params, so empty body

        # Signature is computed on the URL with an empty dictionary of params
        signature = validator.compute_signature(url, params)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Twilio-Signature": signature
        }

        response = httpx.post(
            url,
            headers=headers,
            content=""  # Empty body
        )

        assert response.status_code == 400
        assert "error" in response.json()
        assert response.json()["error"] == "Missing request body"

    def test_signature_with_different_payload(self, api_gateway_url: str, sender_number: str, validator: RequestValidator):
        """Test that signature validation detects payload tampering"""
        url = api_gateway_url

        original_params = {'Body': 'original', 'From': sender_number}
        tampered_params = {'Body': 'tampered', 'From': sender_number}

        # Generate signature for original payload
        signature = validator.compute_signature(url, original_params)

        # Send tampered payload with original signature
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Twilio-Signature": signature
        }

        response = httpx.post(
            url,
            headers=headers,
            content=urlencode(tampered_params)
        )

        assert response.status_code == 403
        assert "error" in response.json()
        assert response.json()["error"] == "Invalid Twilio signature"