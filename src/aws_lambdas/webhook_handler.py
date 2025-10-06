"""
AWS Lambda function for handling Meta WhatsApp webhook event notifications.

This function validates the X-Hub-Signature-256 header to ensure the payload
is genuine, then forwards the event to an AWS SQS queue for processing.
"""

import os
import json
import hmac
import hashlib
import boto3
from typing import Dict, Any


# Initialize SQS client
sqs = boto3.client("sqs")


def verify_signature(payload: str, signature: str, app_secret: str) -> bool:
    """
    Verify the X-Hub-Signature-256 header using HMAC SHA256.

    Args:
        payload: The raw request body as a string
        signature: The signature from X-Hub-Signature-256 header (including 'sha256=' prefix)
        app_secret: The app secret used to generate the signature

    Returns:
        bool: True if signature is valid, False otherwise
    """
    if not signature.startswith("sha256="):
        return False

    # Extract the signature hash (remove 'sha256=' prefix)
    expected_signature = signature[7:]

    # Generate signature using payload and app secret
    generated_signature = hmac.new(
        app_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # Compare signatures using constant-time comparison
    return hmac.compare_digest(generated_signature, expected_signature)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle webhook event notifications from Meta.

    Args:
        event: API Gateway event containing headers and body
        context: Lambda context object

    Returns:
        dict: API Gateway response with status code and body
    """
    # Get configuration from environment
    app_secret = os.environ.get("WHATSAPP_APP_SECRET")
    queue_url = os.environ.get("SQS_QUEUE_URL")

    if not app_secret:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "WHATSAPP_APP_SECRET not configured"})
        }

    if not queue_url:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "SQS_QUEUE_URL not configured"})
        }

    # Get the signature from headers
    headers = event.get("headers", {})
    signature = headers.get("X-Hub-Signature-256") or headers.get("x-hub-signature-256")

    if not signature:
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Missing X-Hub-Signature-256 header"})
        }

    # Get the raw body
    body = event.get("body", "")

    if not body:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing request body"})
        }

    # Verify the signature
    if not verify_signature(body, signature, app_secret):
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "Invalid signature"})
        }

    # Send message to SQS queue
    try:
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=body,
            MessageAttributes={
                "Source": {
                    "StringValue": "WhatsAppWebhook",
                    "DataType": "String"
                }
            }
        )
    except Exception as e:
        # Log error but don't expose details to caller
        print(f"Error sending message to SQS: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to process webhook"})
        }

    # Return 200 OK as required by Meta
    return {
        "statusCode": 200,
        "body": json.dumps({"status": "received"})
    }
