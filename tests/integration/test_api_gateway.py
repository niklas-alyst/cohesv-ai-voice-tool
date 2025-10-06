"""Integration tests for AWS Lambda functions behind API Gateway."""

import pytest
import os
import json
import hmac
import hashlib
from dotenv import load_dotenv
import httpx


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
def verify_token():
    """Get WhatsApp verify token from environment"""
    token = os.getenv("WHATSAPP_VERIFY_TOKEN")
    if not token:
        pytest.skip("WHATSAPP_VERIFY_TOKEN not configured in .env.test")
    return token


@pytest.fixture
def app_secret():
    """Get WhatsApp app secret from environment"""
    secret = os.getenv("WHATSAPP_APP_SECRET")
    if not secret:
        pytest.skip("WHATSAPP_APP_SECRET not configured in .env.test")
    return secret


def generate_signature(payload: str, app_secret: str) -> str:
    """Generate X-Hub-Signature-256 header value"""
    signature = hmac.new(
        app_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"


class TestWebhookVerification:
    """Integration tests for webhook verification endpoint (GET)"""

    def test_successful_verification(self, api_gateway_url, verify_token):
        """Test successful webhook verification with valid parameters"""
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": verify_token,
            "hub.challenge": "test_challenge_12345"
        }

        response = httpx.get(api_gateway_url, params=params)

        assert response.status_code == 200
        assert response.text == "test_challenge_12345"

    def test_invalid_verify_token(self, api_gateway_url):
        """Test verification fails with invalid verify token"""
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "invalid_token_12345",
            "hub.challenge": "test_challenge_12345"
        }

        response = httpx.get(api_gateway_url, params=params)

        assert response.status_code == 403
        assert "error" in response.json()

    def test_invalid_hub_mode(self, api_gateway_url, verify_token):
        """Test verification fails with invalid hub.mode"""
        params = {
            "hub.mode": "unsubscribe",
            "hub.verify_token": verify_token,
            "hub.challenge": "test_challenge_12345"
        }

        response = httpx.get(api_gateway_url, params=params)

        assert response.status_code == 403
        assert "error" in response.json()

    def test_missing_parameters(self, api_gateway_url):
        """Test verification fails with missing query parameters"""
        response = httpx.get(api_gateway_url)

        assert response.status_code == 400
        assert "error" in response.json()


class TestWebhookHandler:
    """Integration tests for webhook event notification handler (POST)"""

    def test_successful_event_notification(self, api_gateway_url, app_secret):
        """Test successful processing of valid event notification"""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123456789",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15551234567",
                                    "phone_number_id": "987654321"
                                }
                            }
                        }
                    ]
                }
            ]
        }

        payload_str = json.dumps(payload)
        signature = generate_signature(payload_str, app_secret)

        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature
        }

        response = httpx.post(
            api_gateway_url,
            headers=headers,
            content=payload_str
        )

        assert response.status_code == 200
        assert response.json().get("status") == "received"

    def test_invalid_signature(self, api_gateway_url):
        """Test event notification fails with invalid signature"""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"id": "123"}]
        }

        payload_str = json.dumps(payload)

        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=invalid_signature_here"
        }

        response = httpx.post(
            api_gateway_url,
            headers=headers,
            content=payload_str
        )

        assert response.status_code == 403
        assert "error" in response.json()

    def test_missing_signature_header(self, api_gateway_url):
        """Test event notification fails without signature header"""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"id": "123"}]
        }

        headers = {
            "Content-Type": "application/json"
        }

        response = httpx.post(
            api_gateway_url,
            headers=headers,
            json=payload
        )

        assert response.status_code == 401
        assert "error" in response.json()

    def test_missing_body(self, api_gateway_url, app_secret):
        """Test event notification fails with missing body"""
        signature = generate_signature("", app_secret)

        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature
        }

        response = httpx.post(
            api_gateway_url,
            headers=headers
        )

        assert response.status_code == 400
        assert "error" in response.json()

    def test_signature_with_different_payload(self, api_gateway_url, app_secret):
        """Test that signature validation detects payload tampering"""
        original_payload = {"object": "whatsapp_business_account", "entry": [{"id": "123"}]}
        tampered_payload = {"object": "whatsapp_business_account", "entry": [{"id": "999"}]}

        # Generate signature for original payload
        signature = generate_signature(json.dumps(original_payload), app_secret)

        # Send tampered payload with original signature
        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature
        }

        response = httpx.post(
            api_gateway_url,
            headers=headers,
            content=json.dumps(tampered_payload)
        )

        assert response.status_code == 403
        assert "error" in response.json()
