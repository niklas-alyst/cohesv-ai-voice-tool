"""
Lambda authorizer for Data API - validates x-api-key header.

This authorizer validates API key authentication for the data-api-server HTTP API.
It reads the API key from AWS Secrets Manager and compares it with the x-api-key header.
"""

import json
import os
import boto3
from typing import Dict, Any

# Initialize Secrets Manager client (cached across invocations)
secrets_client = boto3.client("secretsmanager")

# Cache for the API key (populated on first invocation)
_api_key_cache = None


def get_api_key() -> str:
    """
    Retrieve the API key from AWS Secrets Manager with caching.

    Returns:
        The API key string
    """
    global _api_key_cache

    if _api_key_cache is not None:
        return _api_key_cache

    secret_arn = os.environ.get("API_KEY_SECRET_ARN")
    if not secret_arn:
        raise ValueError("API_KEY_SECRET_ARN environment variable not set")

    try:
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        secret_data = json.loads(response["SecretString"])
        _api_key_cache = secret_data["api_key"]
        return _api_key_cache
    except Exception as e:
        raise ValueError(f"Failed to retrieve API key from Secrets Manager: {str(e)}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda authorizer handler for HTTP API.

    Expected event structure from API Gateway HTTP API:
    {
        "headers": {
            "x-api-key": "the-api-key"
        },
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/files/list"
            }
        },
        "routeArn": "arn:aws:execute-api:region:account:api-id/stage/method/path"
    }

    Returns:
        Authorization response with isAuthorized boolean
    """
    print(f"Authorizer invoked with event: {json.dumps(event)}")

    # Extract the API key from headers (case-insensitive)
    headers = event.get("headers", {})
    provided_key = headers.get("x-api-key") or headers.get("X-API-Key") or headers.get("X-Api-Key")

    if not provided_key:
        print("Authorization denied: Missing x-api-key header")
        return {
            "isAuthorized": False
        }

    try:
        # Get the expected API key from Secrets Manager
        expected_key = get_api_key()

        # Simple string comparison (constant-time comparison would be better for production)
        if provided_key == expected_key:
            print("Authorization granted")
            return {
                "isAuthorized": True,
                "context": {
                    "authMethod": "api-key"
                }
            }
        else:
            print("Authorization denied: Invalid API key")
            return {
                "isAuthorized": False
            }
    except Exception as e:
        print(f"Authorization error: {str(e)}")
        # Deny access on any error
        return {
            "isAuthorized": False
        }
