import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from ai_voice_shared.services.customer_lookup_client import CustomerLookupClient
from ai_voice_shared.settings import CustomerLookupSettings

@pytest.fixture
def mock_aioboto3_session():
    """Fixture to mock aioboto3.Session and its client method."""
    with patch("aioboto3.Session") as mock_session_class:
        mock_session = AsyncMock()
        mock_client = AsyncMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client
        mock_session_class.return_value = mock_session
        yield mock_session_class, mock_client

@pytest.fixture
def mock_customer_lookup_settings():
    """Fixture to provide mock CustomerLookupSettings."""
    return CustomerLookupSettings(
        customer_lookup_lambda_function_name="test-lookup-lambda",
        aws_region="us-east-1"
    )

@pytest.mark.asyncio
async def test_customer_lookup_client_init_with_settings(mock_customer_lookup_settings):
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)
    assert client.lambda_function_name == "test-lookup-lambda"
    assert client.aws_region == "us-east-1"

@pytest.mark.asyncio
async def test_customer_lookup_client_init_without_settings(monkeypatch):
    monkeypatch.setenv("CUSTOMER_LOOKUP_LAMBDA_FUNCTION_NAME", "default-lookup-lambda")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    client = CustomerLookupClient()
    assert client.lambda_function_name == "default-lookup-lambda"
    assert client.aws_region == "us-west-2"

@pytest.mark.asyncio
async def test_fetch_customer_metadata_success(mock_aioboto3_session, mock_customer_lookup_settings):
    mock_session_class, mock_lambda_client = mock_aioboto3_session
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)

    expected_metadata = {
        "customer_id": "cust123",
        "company_id": "comp456",
        "company_name": "TestCo"
    }
    mock_lambda_client.invoke.return_value = {
        "Payload": MagicMock(read=AsyncMock(return_value=json.dumps({
            "statusCode": 200,
            "body": json.dumps(expected_metadata)
        }).encode()))
    }

    metadata = await client.fetch_customer_metadata("whatsapp:+1234567890")
    assert metadata.customer_id == "cust123"
    assert metadata.company_id == "comp456"
    assert metadata.company_name == "TestCo"

    mock_lambda_client.invoke.assert_called_once_with(
        FunctionName="test-lookup-lambda",
        InvocationType='RequestResponse',
        Payload=json.dumps({"phone_number": "+1234567890"})
    )

@pytest.mark.asyncio
async def test_fetch_customer_metadata_not_found(mock_aioboto3_session, mock_customer_lookup_settings):
    mock_session_class, mock_lambda_client = mock_aioboto3_session
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)

    mock_lambda_client.invoke.return_value = {
        "Payload": MagicMock(read=AsyncMock(return_value=json.dumps({
            "statusCode": 404,
            "body": json.dumps({"message": "Customer not found"})
        }).encode()))
    }

    with pytest.raises(ValueError, match="Customer not found for phone number: 1234567890"):
        await client.fetch_customer_metadata("1234567890")

@pytest.mark.asyncio
async def test_fetch_customer_metadata_lambda_error_status(mock_aioboto3_session, mock_customer_lookup_settings):
    mock_session_class, mock_lambda_client = mock_aioboto3_session
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)

    mock_lambda_client.invoke.return_value = {
        "Payload": MagicMock(read=AsyncMock(return_value=json.dumps({
            "statusCode": 500,
            "body": json.dumps({"message": "Internal server error"})
        }).encode()))
    }

    with pytest.raises(ValueError, match="Lambda returned error status 500: {'message': 'Internal server error'}"):
        await client.fetch_customer_metadata("1234567890")

@pytest.mark.asyncio
async def test_fetch_customer_metadata_lambda_function_error(mock_aioboto3_session, mock_customer_lookup_settings):
    mock_session_class, mock_lambda_client = mock_aioboto3_session
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)

    mock_lambda_client.invoke.return_value = {
        "FunctionError": "Unhandled",
        "Payload": MagicMock(read=AsyncMock(return_value=json.dumps({
            "errorMessage": "Something went wrong in Lambda"
        }).encode()))
    }

    with pytest.raises(ValueError, match="Lambda function error: {'errorMessage': 'Something went wrong in Lambda'}"):
        await client.fetch_customer_metadata("1234567890")

@pytest.mark.asyncio
async def test_fetch_customer_metadata_invalid_response_body(mock_aioboto3_session, mock_customer_lookup_settings):
    mock_session_class, mock_lambda_client = mock_aioboto3_session
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)

    mock_lambda_client.invoke.return_value = {
        "Payload": MagicMock(read=AsyncMock(return_value=json.dumps({
            "statusCode": 200,
            "body": json.dumps({"not_a_customer_metadata_field": "value"}) # Invalid structure
        }).encode()))
    }

    with pytest.raises(ValidationError):
        await client.fetch_customer_metadata("1234567890")

@pytest.mark.asyncio
async def test_fetch_customer_metadata_general_exception(mock_aioboto3_session, mock_customer_lookup_settings):
    mock_session_class, mock_lambda_client = mock_aioboto3_session
    client = CustomerLookupClient(settings=mock_customer_lookup_settings)

    mock_lambda_client.invoke.side_effect = Exception("Network error")

    with pytest.raises(ValueError, match="Customer lookup failed: Network error"):
        await client.fetch_customer_metadata("1234567890")
