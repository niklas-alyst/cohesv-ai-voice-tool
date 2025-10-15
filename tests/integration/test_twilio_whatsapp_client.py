import pytest
import os
from dotenv import load_dotenv
from voice_parser.services.twilio_whatsapp_client import TwilioWhatsAppClient
from voice_parser.core.settings import TwilioWhatsAppSettings


@pytest.fixture(scope="session", autouse=True)
def load_test_env():
    """Load test environment variables from .env.test"""
    load_dotenv(".env.test")


@pytest.fixture
def test_twilio_settings():
    """Create Twilio settings using test environment variables"""
    return TwilioWhatsAppSettings(
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
        twilio_whatsapp_number=os.getenv("TWILIO_WHATSAPP_NUMBER"),
    )


@pytest.fixture
def twilio_client(test_twilio_settings):
    """Create Twilio client with test settings"""
    # Skip tests if essential settings are missing
    if not all([
        test_twilio_settings.twilio_account_sid,
        test_twilio_settings.twilio_auth_token,
        test_twilio_settings.twilio_whatsapp_number
    ]):
        pytest.skip("Twilio credentials not fully configured in .env.test")
    return TwilioWhatsAppClient(settings=test_twilio_settings)


class TestTwilioWhatsAppClientIntegration:
    """Integration tests for Twilio WhatsApp client using real API"""

    @pytest.mark.asyncio
    async def test_send_message(self, twilio_client):
        """Test sending a real WhatsApp message"""
        recipient_phone = os.getenv("TWILIO_RECIPIENT_PHONE")
        if not recipient_phone:
            pytest.skip("TWILIO_RECIPIENT_PHONE not set in .env.test")

        body = "Hello from the integration test!"
        response = await twilio_client.send_message(
            recipient_phone=recipient_phone,
            body=body
        )

        assert response is not None
        assert "sid" in response
        assert response["sid"].startswith("SM")
        assert response["status"] in ["queued", "sending"]
        assert response["error_code"] is None
        assert response["to"] == f"whatsapp:{recipient_phone}"

    @pytest.mark.asyncio
    async def test_send_templated_message(self, twilio_client):
        """Test sending a real templated WhatsApp message"""
        recipient_phone = os.getenv("TWILIO_RECIPIENT_PHONE")
        if not recipient_phone:
            pytest.skip("TWILIO_RECIPIENT_PHONE not set in .env.test")

        content_sid = os.getenv("TWILIO_CONTENT_SID")
        if not content_sid:
            pytest.skip("TWILIO_CONTENT_SID not set in .env.test")

        content_variables = {"1": "John Doe"}
        response = await twilio_client.send_templated_message(
            recipient_phone=recipient_phone,
            content_sid=content_sid,
            content_variables=content_variables,
        )

        assert response is not None
        assert "sid" in response
        assert response["sid"].startswith("SM")
        assert response["status"] in ["queued", "sending"]
        assert response["error_code"] is None
        assert response["to"] == f"whatsapp:{recipient_phone}"
