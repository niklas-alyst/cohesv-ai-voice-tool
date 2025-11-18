import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import ValidationError
import httpx

from ai_voice_shared.services.customer_lookup_client import CustomerLookupClient
from ai_voice_shared.settings import CustomerLookupSettings

@pytest.fixture
def mock_customer_lookup_settings():
    """Fixture to provide mock CustomerLookupSettings."""
    return CustomerLookupSettings(
        wunse_api_base_url="https://api.example.com",
        wunse_api_key="test-api-key-123"
    )

@pytest.mark.asyncio
async def test_customer_lookup_client_init_with_settings(mock_customer_lookup_settings):
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)
    assert client.api_base_url == "https://api.example.com"
    assert client.api_key == "test-api-key-123"

@pytest.mark.asyncio
async def test_customer_lookup_client_init_without_settings(monkeypatch):
    monkeypatch.setenv("WUNSE_API_BASE_URL", "https://api.default.com")
    monkeypatch.setenv("WUNSE_API_KEY", "default-api-key")
    client = CustomerLookupClient()
    assert client.api_base_url == "https://api.default.com"
    assert client.api_key == "default-api-key"

@pytest.mark.asyncio
async def test_fetch_customer_metadata_success(mock_customer_lookup_settings):
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)

    expected_metadata = {
        "customer_id": "cust123",
        "company_id": "comp456",
        "company_name": "TestCo"
    }

    with patch("ai_voice_shared.services.customer_lookup_client.httpx.AsyncClient") as mock_async_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_metadata
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_async_client_class.return_value = mock_client

        metadata = await client.fetch_customer_metadata("whatsapp:+1234567890")

        assert metadata.customer_id == "cust123"
        assert metadata.company_id == "comp456"
        assert metadata.company_name == "TestCo"

        mock_client.get.assert_called_once_with(
            "https://api.example.com/customer/lookup",
            params={"phone_number": "+1234567890"},
            headers={"x-api-key": "test-api-key-123"},
            timeout=10.0
        )

@pytest.mark.asyncio
async def test_fetch_customer_metadata_not_found(mock_customer_lookup_settings):
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)

    with patch("ai_voice_shared.services.customer_lookup_client.httpx.AsyncClient") as mock_async_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Customer not found for phone: 1234567890"}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_async_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="Customer not found for phone: 1234567890"):
            await client.fetch_customer_metadata("1234567890")

@pytest.mark.asyncio
async def test_fetch_customer_metadata_server_error(mock_customer_lookup_settings):
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)

    with patch("ai_voice_shared.services.customer_lookup_client.httpx.AsyncClient") as mock_async_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal server error"}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_async_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="Customer lookup failed: HTTP 500"):
            await client.fetch_customer_metadata("1234567890")

@pytest.mark.asyncio
async def test_fetch_customer_metadata_unauthorized(mock_customer_lookup_settings):
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)

    with patch("ai_voice_shared.services.customer_lookup_client.httpx.AsyncClient") as mock_async_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_async_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="Customer lookup failed: Unauthorized"):
            await client.fetch_customer_metadata("1234567890")

@pytest.mark.asyncio
async def test_fetch_customer_metadata_bad_request(mock_customer_lookup_settings):
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)

    with patch("ai_voice_shared.services.customer_lookup_client.httpx.AsyncClient") as mock_async_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Missing phone_number parameter"}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_async_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="Customer lookup failed: Missing phone_number parameter"):
            await client.fetch_customer_metadata("1234567890")

@pytest.mark.asyncio
async def test_fetch_customer_metadata_invalid_response_body(mock_customer_lookup_settings):
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)

    with patch("ai_voice_shared.services.customer_lookup_client.httpx.AsyncClient") as mock_async_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"not_a_customer_metadata_field": "value"}  # Invalid structure
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_async_client_class.return_value = mock_client

        with pytest.raises(ValidationError):
            await client.fetch_customer_metadata("1234567890")

@pytest.mark.asyncio
async def test_fetch_customer_metadata_http_exception(mock_customer_lookup_settings):
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)

    with patch("ai_voice_shared.services.customer_lookup_client.httpx.AsyncClient") as mock_async_client_class:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("Network error", request=None))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_async_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="Customer lookup failed:"):
            await client.fetch_customer_metadata("1234567890")
