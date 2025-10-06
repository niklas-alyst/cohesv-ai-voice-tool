"""
AWS Lambda function for verifying Meta WhatsApp webhook subscriptions.

This function handles GET requests from Meta's API to verify webhook endpoints.
It validates the verify token and returns the challenge value.
"""

import os
import json


def lambda_handler(event, context):
    """
    Handle webhook verification requests from Meta.

    Args:
        event: API Gateway event containing query string parameters
        context: Lambda context object

    Returns:
        dict: API Gateway response with status code and body
    """
    # Get the verify token from environment
    expected_verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN")

    if not expected_verify_token:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "WHATSAPP_VERIFY_TOKEN not configured"})
        }

    # Extract query parameters
    params = event.get("queryStringParameters", {})

    if not params:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing query parameters"})
        }

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    # Verify that mode is 'subscribe'
    if mode != "subscribe":
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "Invalid hub.mode"})
        }

    # Verify the token matches
    if token != expected_verify_token:
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "Invalid verify token"})
        }

    # Return the challenge value
    return {
        "statusCode": 200,
        "body": challenge,
        "headers": {
            "Content-Type": "text/plain"
        }
    }
