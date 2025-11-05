"""
AWS Lambda function for handling Twilio's WhatsApp webhook event notifications.

This function validates the X-Twilio-Signature header using the Twilio Auth Token to ensure the payload
is genuine, then forwards the event to an AWS SQS queue for processing.
"""

import os
import json
import boto3
import logging
import asyncio
from typing import Dict, Any
from urllib.parse import parse_qs

# Twilio's request validator
from twilio.request_validator import RequestValidator

# Customer lookup service and models from shared library
from ai_voice_shared import CustomerLookupClient, TwilioWebhookPayload

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize SQS client
sqs = boto3.client("sqs")

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle webhook event notifications from Twilio.
    """
    logger.info(f"Triggering handler with event: {event}")
    # Get configuration from environment
    twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    sqs_queue_url = os.environ.get("SQS_QUEUE_URL")

    if not twilio_auth_token:
        err_msg = "TWILIO_AUTH_TOKEN not configured"
        status_code = 500 
        logger.error(f"{err_msg}, returning {status_code}")
        return {"statusCode": status_code, "body": json.dumps({"error": err_msg})}
    
    if not sqs_queue_url:
        err_msg = "SQS_QUEUE_URL not configured"
        status_code = 500 
        logger.error(f"{err_msg}, returning {status_code}")
        return {"statusCode": status_code, "body": json.dumps({"error": err_msg})}

    # Initialize customer lookup service for phone number authorization
    try:
        customer_lookup_client = CustomerLookupClient()
    except Exception as e:
        err_msg = f"Failed to initialize customer lookup service: {str(e)}"
        status_code = 500
        logger.error(f"{err_msg}, returning {status_code}")
        return {"statusCode": status_code, "body": json.dumps({"error": err_msg})}

    # Initialize the validator with your Auth Token
    validator = RequestValidator(twilio_auth_token)

    # Get the signature from headers (case-insensitive)
    headers = event.get("headers", {})
    signature = headers.get("X-Twilio-Signature") or headers.get("x-twilio-signature")

    if not signature:
        err_msg = "Missing X-Twilio-Signature header"
        status_code = 401
        logger.error(f"{err_msg}, returning {status_code}")
        return {"statusCode": status_code, "body": json.dumps({"error": err_msg})}

    # Construct the full URL that Twilio requested
    # API Gateway provides this information in the event object
    request_url = f"https://{event['requestContext']['domainName']}{event['requestContext']['path']}"

    # Include query string parameters if present
    query_params = event.get("queryStringParameters")
    if query_params:
        query_string = "&".join([f"{k}={v}" for k, v in sorted(query_params.items())])
        request_url = f"{request_url}?{query_string}"

    # Get the raw body and parse it
    raw_body = event.get("body", "")
    if not raw_body:
        err_msg = "Missing request body"
        status_code = 400
        logger.error(f"{err_msg}, returning {status_code}")
        return {"statusCode": status_code, "body": json.dumps({"error": err_msg})}

    # The validator needs the POST parameters as a dictionary
    # IMPORTANT: keep_blank_values=True is required to preserve empty parameters like Body=
    # Twilio includes empty parameters in signature calculation
    post_params = {k: v[0] for k, v in parse_qs(raw_body, keep_blank_values=True).items()}

    # Debug logging for signature validation
    logger.info(f"Validating signature for URL: {request_url}")
    logger.info(f"POST parameters: {post_params}")
    logger.info(f"Signature: {signature}")

    # Check phone number authorization using customer lookup API
    from_number = post_params.get("From", "")
    if not from_number:
        err_msg = "Missing 'From' field in request"
        status_code = 400
        logger.error(f"{err_msg}, returning {status_code}")
        return {"statusCode": status_code, "body": json.dumps({"error": err_msg})}

    try:
        # Attempt to fetch customer metadata (this validates authorization)
        customer_metadata = asyncio.run(customer_lookup_client.fetch_customer_metadata(from_number))
        logger.info(f"Phone number {from_number} authorized for customer: {customer_metadata.customer_id}, company: {customer_metadata.company_name}")
    except Exception as e:
        # If lookup fails (404, validation error, etc.), phone number is not authorized
        err_msg = f"Phone number not authorized: {from_number}"
        status_code = 401
        logger.error(f"{err_msg} - Lookup failed with: {str(e)}")
        return {"statusCode": status_code, "body": json.dumps({"error": err_msg})}


    # Validate the request
    if not validator.validate(request_url, post_params, signature):
        err_msg = "Invalid Twilio signature"
        status_code = 403
        logger.error(f"{err_msg}, returning {status_code}")
        return {"statusCode": status_code, "body": json.dumps({"error": err_msg})}

    # At this point, the request is verified.
    # The post_params dictionary contains the message data.
    # Example: {'From': 'whatsapp:+1...', 'Body': 'Hello', 'SmsMessageSid': 'SM...'}

    # Validate the payload structure using the shared TwilioWebhookPayload model
    try:
        validated_payload = TwilioWebhookPayload(**post_params)
        logger.info(f"Validated webhook payload for message {validated_payload.MessageSid}")
    except Exception as e:
        err_msg = f"Invalid webhook payload structure: {str(e)}"
        status_code = 400
        logger.error(f"{err_msg}, returning {status_code}")
        return {"statusCode": status_code, "body": json.dumps({"error": err_msg})}

    try:
        # Send the validated Twilio payload to SQS for processing
        message_body = validated_payload.model_dump_json()
        logger.info(f"Sending message {message_body} to SQS")
        sqs.send_message(
            QueueUrl=sqs_queue_url,
            # We send the dictionary as a JSON string for easy processing later
            MessageBody=message_body, 
            MessageAttributes={
                "Source": {
                    "StringValue": "TwilioWhatsAppWebhook",
                    "DataType": "String"
                }
            }
        )
    except Exception as e:
        logger.error(f"Error sending message to SQS: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to process webhook"})}

    # Return 200 OK to Twilio
    logger.info("Lambda finished successfully, returning 200")
    return {"statusCode": 200, "body": json.dumps({"status": "received"})}
