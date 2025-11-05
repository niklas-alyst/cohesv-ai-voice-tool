"""Integration tests for customer-lookup-server Lambda function."""

import json

import boto3
import pytest


@pytest.fixture
def lambda_client():
    """Create boto3 Lambda client."""
    return boto3.client(
        "lambda",
        region_name="ap-southeast-2",
    )


@pytest.fixture
def lambda_function_name():
    """Lambda function name to test."""
    return "ai-voice-tool-customer-lookup-server"


class TestLambdaIntegration:
    """Integration tests for Lambda function invocation."""

    def test_lambda_invoke_with_valid_phone_number(
        self, lambda_client, lambda_function_name
    ):
        """Test Lambda invocation with a valid phone number."""
        # Prepare test event - using hardcoded phone number from repository
        event = {"phone_number": "+61400000000"}

        # Invoke Lambda
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
        assert "statusCode" in payload

        # The function should return either 200 (found) or 404 (not found)
        # Both are valid responses indicating the Lambda is working
        assert payload["statusCode"] in [200, 404]

        # Parse body
        body = json.loads(payload["body"])
        print(f"Response body: {json.dumps(body, indent=2)}")

        if payload["statusCode"] == 200:
            # If customer found, validate structure
            assert "customer_id" in body
            assert "company_id" in body
            assert "company_name" in body
        else:
            # If not found, validate error message
            assert "error" in body
            assert "Customer not found" in body["error"]

    def test_lambda_invoke_with_whatsapp_prefix(
        self, lambda_client, lambda_function_name
    ):
        """Test Lambda invocation with whatsapp: prefix."""
        # Prepare test event with whatsapp prefix - using hardcoded phone number
        event = {"phone_number": "whatsapp:+61400000000"}

        # Invoke Lambda
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        # Parse response
        payload = json.loads(response["Payload"].read())

        # Assertions
        assert response["StatusCode"] == 200
        assert payload["statusCode"] in [200, 404]

    def test_lambda_invoke_missing_phone_number(
        self, lambda_client, lambda_function_name
    ):
        """Test Lambda invocation without phone number."""
        # Prepare test event without phone_number
        event = {}

        # Invoke Lambda
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
        assert payload["statusCode"] == 400

        # Validate error message
        body = json.loads(payload["body"])
        assert "error" in body
        assert "Missing phone_number parameter" in body["error"]

    def test_lambda_invoke_with_nonexistent_phone_number(
        self, lambda_client, lambda_function_name
    ):
        """Test Lambda invocation with a phone number not in the repository."""
        # Prepare test event with a phone number that doesn't exist
        event = {"phone_number": "+14155552671"}

        # Invoke Lambda
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        # Parse response
        payload = json.loads(response["Payload"].read())

        # Assertions
        assert response["StatusCode"] == 200
        assert payload["statusCode"] == 404

        # Validate error message
        body = json.loads(payload["body"])
        assert "error" in body
        assert "Customer not found for phone: +14155552671" in body["error"]

    def test_lambda_invoke_async(self, lambda_client, lambda_function_name):
        """Test async Lambda invocation."""
        # Prepare test event - using hardcoded phone number
        event = {"phone_number": "+61400000000"}

        # Invoke Lambda asynchronously
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType="Event",  # Async invocation
            Payload=json.dumps(event),
        )

        # For async invocation, we just check that it was accepted
        assert response["StatusCode"] == 202
