"""Lambda handler for customer lookup service."""

import json
import logging
import os
from typing import Any, Dict

from customer_lookup_server.core.repository import CustomerRepository

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize repository with environment variables
s3_bucket = os.environ.get("S3_BUCKET_NAME", "cohesv-ai-voice-tool")
s3_key = os.environ.get("CUSTOMERS_S3_KEY", "customers.json")
repository = CustomerRepository(s3_bucket=s3_bucket, s3_key=s3_key)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for customer lookup by phone number.

    Input event:
    {
        "phone_number": "+14155552671"
    }

    Output (success):
    {
        "statusCode": 200,
        "body": "{\"customer_id\": \"cust_123\", \"company_id\": \"comp_456\", \"company_name\": \"Acme Corp\"}"
    }

    Output (not found):
    {
        "statusCode": 404,
        "body": "{\"error\": \"Customer not found for phone: +14155552671\"}"
    }

    Args:
        event: Lambda event containing phone_number
        context: Lambda context object

    Returns:
        API Gateway-style response with statusCode and body
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")

        # Extract phone number from event
        phone_number = event.get("phone_number")

        if not phone_number:
            logger.error("Missing phone_number parameter in event")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing phone_number parameter"})
            }

        # Clean phone number (remove whatsapp: prefix if present)
        clean_phone_number = phone_number.replace("whatsapp:", "")
        logger.info(f"Looking up customer for phone number: {clean_phone_number}")

        # Query repository for customer data
        customer_data = repository.find_by_phone_number(clean_phone_number)

        if not customer_data:
            logger.warning(f"Customer not found for phone number: {clean_phone_number}")
            return {
                "statusCode": 404,
                "body": json.dumps({"error": f"Customer not found for phone: {clean_phone_number}"})
            }

        logger.info(f"Successfully found customer: {customer_data['customer_id']}")
        return {
            "statusCode": 200,
            "body": json.dumps(customer_data)
        }

    except Exception as e:
        logger.error(f"Error processing customer lookup: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"})
        }
