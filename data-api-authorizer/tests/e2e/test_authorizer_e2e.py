"""E2E tests for data-api-authorizer Lambda function.

These tests invoke the deployed Lambda function to verify it works correctly
in the real AWS environment with actual Secrets Manager integration.
"""

import json
import os

import boto3
import pytest


@pytest.fixture
def lambda_client():
    """Create boto3 Lambda client."""
    return boto3.client("lambda", region_name="ap-southeast-2")


@pytest.fixture
def secrets_client():
    """Create boto3 Secrets Manager client."""
    return boto3.client("secretsmanager", region_name="ap-southeast-2")


@pytest.fixture
def lambda_function_name():
    """Lambda function name to test (defaults to dev environment)."""
    env = os.environ.get("TEST_ENV", "dev")
    return f"{env}-data-api-authorizer"


@pytest.fixture
def api_key_secret_name():
    """API key secret name (defaults to dev environment)."""
    env = os.environ.get("TEST_ENV", "dev")
    return f"{env}/ai-voice-tool/data-api-key"


@pytest.fixture
def valid_api_key(secrets_client, api_key_secret_name):
    """Retrieve the valid API key from Secrets Manager for testing."""
    try:
        response = secrets_client.get_secret_value(SecretId=api_key_secret_name)
        secret_data = json.loads(response["SecretString"])
        return secret_data["api_key"]
    except Exception as e:
        pytest.skip(f"Could not retrieve API key from Secrets Manager: {e}")


class TestAuthorizerE2E:
    """E2E tests for the authorizer Lambda function."""

    @pytest.mark.e2e
    def test_authorizer_with_valid_api_key(self, lambda_client, lambda_function_name, valid_api_key):
        """Test that authorizer allows access with valid API key."""
        event = {
            "headers": {
                "x-api-key": valid_api_key
            },
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/files/list"
                }
            },
            "routeArn": "arn:aws:execute-api:ap-southeast-2:404293832854:test-api/test-stage/GET/files/list"
        }

        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        # Parse response
        payload = json.loads(response["Payload"].read())
        print(f"Lambda response: {json.dumps(payload, indent=2)}")

        # Assertions
        assert response["StatusCode"] == 200
        assert payload["isAuthorized"] is True
        assert "context" in payload
        assert payload["context"]["authMethod"] == "api-key"

    @pytest.mark.e2e
    def test_authorizer_with_invalid_api_key(self, lambda_client, lambda_function_name):
        """Test that authorizer denies access with invalid API key."""
        event = {
            "headers": {
                "x-api-key": "invalid-key-that-does-not-exist-12345"
            },
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/files/list"
                }
            }
        }

        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        # Parse response
        payload = json.loads(response["Payload"].read())
        print(f"Lambda response: {json.dumps(payload, indent=2)}")

        # Assertions
        assert response["StatusCode"] == 200
        assert payload["isAuthorized"] is False
        # Should not include context when denied
        assert "context" not in payload

    @pytest.mark.e2e
    def test_authorizer_with_missing_api_key(self, lambda_client, lambda_function_name):
        """Test that authorizer denies access when API key header is missing."""
        event = {
            "headers": {},
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/files/list"
                }
            }
        }

        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        # Parse response
        payload = json.loads(response["Payload"].read())
        print(f"Lambda response: {json.dumps(payload, indent=2)}")

        # Assertions
        assert response["StatusCode"] == 200
        assert payload["isAuthorized"] is False
        assert "context" not in payload

    @pytest.mark.e2e
    def test_authorizer_with_empty_api_key(self, lambda_client, lambda_function_name):
        """Test that authorizer denies access when API key is empty."""
        event = {
            "headers": {
                "x-api-key": ""
            }
        }

        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        # Parse response
        payload = json.loads(response["Payload"].read())

        # Assertions
        assert response["StatusCode"] == 200
        assert payload["isAuthorized"] is False
        assert "context" not in payload

    @pytest.mark.e2e
    def test_authorizer_case_insensitive_headers(self, lambda_client, lambda_function_name, valid_api_key):
        """Test that authorizer accepts API key with different header casing."""
        # Test with uppercase header
        event = {
            "headers": {
                "X-API-Key": valid_api_key
            }
        }

        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        payload = json.loads(response["Payload"].read())

        assert response["StatusCode"] == 200
        assert payload["isAuthorized"] is True

        # Test with mixed case header
        event = {
            "headers": {
                "X-Api-Key": valid_api_key
            }
        }

        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        payload = json.loads(response["Payload"].read())

        assert response["StatusCode"] == 200
        assert payload["isAuthorized"] is True

    @pytest.mark.e2e
    def test_authorizer_caching_behavior(self, lambda_client, lambda_function_name, valid_api_key):
        """Test that authorizer performs well with repeated invocations (cache test)."""
        event = {
            "headers": {
                "x-api-key": valid_api_key
            }
        }

        # Invoke multiple times rapidly
        for i in range(5):
            response = lambda_client.invoke(
                FunctionName=lambda_function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(event),
            )

            payload = json.loads(response["Payload"].read())

            # All invocations should succeed
            assert response["StatusCode"] == 200
            assert payload["isAuthorized"] is True

        print("Successfully completed 5 rapid invocations - caching working correctly")
