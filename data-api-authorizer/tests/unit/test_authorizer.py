"""Unit tests for data-api-authorizer Lambda function."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Mock the boto3 client before importing authorizer to avoid NoRegionError
with patch("boto3.client") as mock_client:
    mock_client.return_value = MagicMock()
    from authorizer import get_api_key, lambda_handler


@pytest.fixture
def mock_secrets_client():
    """Fixture to mock the boto3 Secrets Manager client."""
    with patch("authorizer.secrets_client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_env():
    """Fixture to mock environment variables."""
    with patch.dict(os.environ, {"API_KEY_SECRET_ARN": "arn:aws:secretsmanager:region:account:secret:test-secret"}):
        yield


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset the API key cache before each test."""
    import authorizer
    authorizer._api_key_cache = None
    yield
    authorizer._api_key_cache = None


class TestGetApiKey:
    """Unit tests for get_api_key function."""

    @pytest.mark.unit
    def test_get_api_key_success(self, mock_secrets_client, mock_env):
        """Test successful API key retrieval from Secrets Manager."""
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "test-api-key-12345"})
        }

        result = get_api_key()

        assert result == "test-api-key-12345"
        mock_secrets_client.get_secret_value.assert_called_once_with(
            SecretId="arn:aws:secretsmanager:region:account:secret:test-secret"
        )

    @pytest.mark.unit
    def test_get_api_key_caching(self, mock_secrets_client, mock_env):
        """Test that API key is cached after first retrieval."""
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "test-api-key-12345"})
        }

        # Call twice
        result1 = get_api_key()
        result2 = get_api_key()

        # Both should return the same value
        assert result1 == "test-api-key-12345"
        assert result2 == "test-api-key-12345"

        # But Secrets Manager should only be called once (caching)
        mock_secrets_client.get_secret_value.assert_called_once()

    @pytest.mark.unit
    def test_get_api_key_missing_env_var(self, mock_secrets_client):
        """Test error handling when API_KEY_SECRET_ARN is not set."""
        with pytest.raises(ValueError) as exc_info:
            get_api_key()

        assert "API_KEY_SECRET_ARN environment variable not set" in str(exc_info.value)
        mock_secrets_client.get_secret_value.assert_not_called()

    @pytest.mark.unit
    def test_get_api_key_secrets_manager_error(self, mock_secrets_client, mock_env):
        """Test error handling when Secrets Manager call fails."""
        mock_secrets_client.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Secret not found"}},
            "GetSecretValue"
        )

        with pytest.raises(ValueError) as exc_info:
            get_api_key()

        assert "Failed to retrieve API key from Secrets Manager" in str(exc_info.value)

    @pytest.mark.unit
    def test_get_api_key_invalid_json(self, mock_secrets_client, mock_env):
        """Test error handling when secret contains invalid JSON."""
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": "not-valid-json"
        }

        with pytest.raises(ValueError) as exc_info:
            get_api_key()

        assert "Failed to retrieve API key from Secrets Manager" in str(exc_info.value)

    @pytest.mark.unit
    def test_get_api_key_missing_api_key_field(self, mock_secrets_client, mock_env):
        """Test error handling when secret JSON is missing api_key field."""
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"wrong_field": "value"})
        }

        with pytest.raises(ValueError) as exc_info:
            get_api_key()

        assert "Failed to retrieve API key from Secrets Manager" in str(exc_info.value)


class TestLambdaHandler:
    """Unit tests for lambda_handler function."""

    @pytest.mark.unit
    def test_lambda_handler_success_lowercase_header(self, mock_secrets_client, mock_env):
        """Test successful authorization with lowercase x-api-key header."""
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "test-api-key-12345"})
        }

        event = {
            "headers": {
                "x-api-key": "test-api-key-12345"
            },
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/files/list"
                }
            },
            "routeArn": "arn:aws:execute-api:region:account:api-id/stage/method/path"
        }

        result = lambda_handler(event, None)

        assert result == {
            "isAuthorized": True,
            "context": {
                "authMethod": "api-key"
            }
        }

    @pytest.mark.unit
    def test_lambda_handler_success_uppercase_header(self, mock_secrets_client, mock_env):
        """Test successful authorization with X-API-Key header."""
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "test-api-key-12345"})
        }

        event = {
            "headers": {
                "X-API-Key": "test-api-key-12345"
            }
        }

        result = lambda_handler(event, None)

        assert result["isAuthorized"] is True
        assert result["context"]["authMethod"] == "api-key"

    @pytest.mark.unit
    def test_lambda_handler_success_mixed_case_header(self, mock_secrets_client, mock_env):
        """Test successful authorization with X-Api-Key header."""
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "test-api-key-12345"})
        }

        event = {
            "headers": {
                "X-Api-Key": "test-api-key-12345"
            }
        }

        result = lambda_handler(event, None)

        assert result["isAuthorized"] is True
        assert result["context"]["authMethod"] == "api-key"

    @pytest.mark.unit
    def test_lambda_handler_missing_header(self, mock_secrets_client, mock_env):
        """Test authorization failure when x-api-key header is missing."""
        event = {
            "headers": {}
        }

        result = lambda_handler(event, None)

        assert result == {"isAuthorized": False}
        mock_secrets_client.get_secret_value.assert_not_called()

    @pytest.mark.unit
    def test_lambda_handler_missing_headers_key(self, mock_secrets_client, mock_env):
        """Test authorization failure when headers key is missing from event."""
        event = {}

        result = lambda_handler(event, None)

        assert result == {"isAuthorized": False}
        mock_secrets_client.get_secret_value.assert_not_called()

    @pytest.mark.unit
    def test_lambda_handler_invalid_api_key(self, mock_secrets_client, mock_env):
        """Test authorization failure with invalid API key."""
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "correct-api-key-12345"})
        }

        event = {
            "headers": {
                "x-api-key": "wrong-api-key"
            }
        }

        result = lambda_handler(event, None)

        assert result == {"isAuthorized": False}

    @pytest.mark.unit
    def test_lambda_handler_empty_api_key(self, mock_secrets_client, mock_env):
        """Test authorization failure with empty API key."""
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "test-api-key-12345"})
        }

        event = {
            "headers": {
                "x-api-key": ""
            }
        }

        result = lambda_handler(event, None)

        assert result == {"isAuthorized": False}

    @pytest.mark.unit
    def test_lambda_handler_secrets_manager_error(self, mock_secrets_client, mock_env):
        """Test authorization failure when Secrets Manager call fails."""
        mock_secrets_client.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "GetSecretValue"
        )

        event = {
            "headers": {
                "x-api-key": "test-api-key-12345"
            }
        }

        result = lambda_handler(event, None)

        assert result == {"isAuthorized": False}

    @pytest.mark.unit
    def test_lambda_handler_missing_env_var(self, mock_secrets_client):
        """Test authorization failure when API_KEY_SECRET_ARN is not set."""
        event = {
            "headers": {
                "x-api-key": "test-api-key-12345"
            }
        }

        result = lambda_handler(event, None)

        assert result == {"isAuthorized": False}

    @pytest.mark.unit
    def test_lambda_handler_caches_api_key(self, mock_secrets_client, mock_env):
        """Test that API key is cached across multiple handler invocations."""
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "test-api-key-12345"})
        }

        event = {
            "headers": {
                "x-api-key": "test-api-key-12345"
            }
        }

        # Call handler multiple times
        result1 = lambda_handler(event, None)
        result2 = lambda_handler(event, None)
        result3 = lambda_handler(event, None)

        # All should succeed
        assert result1["isAuthorized"] is True
        assert result2["isAuthorized"] is True
        assert result3["isAuthorized"] is True

        # But Secrets Manager should only be called once
        mock_secrets_client.get_secret_value.assert_called_once()

    @pytest.mark.unit
    def test_lambda_handler_with_additional_headers(self, mock_secrets_client, mock_env):
        """Test authorization with other headers present."""
        mock_secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "test-api-key-12345"})
        }

        event = {
            "headers": {
                "x-api-key": "test-api-key-12345",
                "content-type": "application/json",
                "user-agent": "test-client"
            }
        }

        result = lambda_handler(event, None)

        assert result["isAuthorized"] is True
        assert result["context"]["authMethod"] == "api-key"

    @pytest.mark.unit
    def test_lambda_handler_generic_exception(self, mock_secrets_client, mock_env):
        """Test authorization failure when an unexpected exception occurs."""
        mock_secrets_client.get_secret_value.side_effect = Exception("Unexpected error")

        event = {
            "headers": {
                "x-api-key": "test-api-key-12345"
            }
        }

        result = lambda_handler(event, None)

        assert result == {"isAuthorized": False}
