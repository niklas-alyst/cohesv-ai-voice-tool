"""
AWS Lambda function for handling Twilio's WhatsApp webhook event notifications.

This function validates the X-Twilio-Signature header using the Twilio Auth Token to ensure the payload
is genuine, then forwards the event to an AWS SQS queue for processing.
"""

import os
import json
import boto3
from typing import Dict, Any
from urllib.parse import parse_qs

# Twilio's request validator
from twilio.request_validator import RequestValidator

# Initialize SQS client
sqs = boto3.client("sqs")

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle webhook event notifications from Twilio.
    """
    # Get configuration from environment
    twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    queue_url = os.environ.get("SQS_QUEUE_URL")

    if not twilio_auth_token:
        print("TWILIO_AUTH_TOKEN not configured, Returning 500")
        return {"statusCode": 500, "body": json.dumps({"error": "TWILIO_AUTH_TOKEN not configured"})}
    if not queue_url:
        print("SQS_QUEUE_URL not configured, Returning 500")
        return {"statusCode": 500, "body": json.dumps({"error": "SQS_QUEUE_URL not configured"})}

    # Initialize the validator with your Auth Token
    validator = RequestValidator(twilio_auth_token)

    # Get the signature from headers (case-insensitive)
    headers = event.get("headers", {})
    signature = headers.get("X-Twilio-Signature") or headers.get("x-twilio-signature")

    if not signature:
        return {"statusCode": 401, "body": json.dumps({"error": "Missing X-Twilio-Signature header"})}

    # Construct the full URL that Twilio requested
    # API Gateway provides this information in the event object
    request_url = f"https://{event['requestContext']['domainName']}{event['requestContext']['path']}"
    
    # Get the raw body and parse it
    raw_body = event.get("body", "")
    if not raw_body:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing request body"})}

    # The validator needs the POST parameters as a dictionary
    post_params = {k: v[0] for k, v in parse_qs(raw_body).items()}

    # Validate the request
    if not validator.validate(request_url, post_params, signature):
        return {"statusCode": 403, "body": json.dumps({"error": "Invalid Twilio signature"})}

    # At this point, the request is verified.
    # The post_params dictionary contains the message data.
    # Example: {'From': 'whatsapp:+1...', 'Body': 'Hello', 'SmsMessageSid': 'SM...'}
    
    try:
        # Send the verified Twilio payload to SQS for processing
        sqs.send_message(
            QueueUrl=queue_url,
            # We send the dictionary as a JSON string for easy processing later
            MessageBody=json.dumps(post_params), 
            MessageAttributes={
                "Source": {
                    "StringValue": "TwilioWhatsAppWebhook",
                    "DataType": "String"
                }
            }
        )
    except Exception as e:
        print(f"Error sending message to SQS: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to process webhook"})}

    # Return 200 OK to Twilio
    return {"statusCode": 200, "body": json.dumps({"status": "received"})}
