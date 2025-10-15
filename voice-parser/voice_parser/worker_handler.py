"""
AWS Lambda function for processing WhatsApp voice messages from SQS queue.

This worker function:
1. Receives messages from SQS containing WhatsApp webhook payloads
2. Downloads audio files from WhatsApp
3. Uploads to S3 for persistence
4. Transcribes audio using Whisper API
5. Structures the transcription using LLM
"""

import json
import logging
from typing import Any, Dict

from voice_parser.models import TwilioWebhookPayload
from voice_parser.core.processor import process_message

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for SQS events containing WhatsApp webhook payloads.

    Args:
        event: SQS event with Records
        context: Lambda context object

    Returns:
        dict: Processing result with batchItemFailures for partial failures
    """
    import asyncio

    logger.info(f"Received SQS event with {len(event.get('Records', []))} records")

    batch_item_failures = []

    for record in event.get("Records", []):
        message_id = record.get("messageId")

        try:
            # Parse SQS message body
            body = record.get("body", "")
            payload_dict = json.loads(body)

            # Validate and parse WhatsApp payload
            payload = TwilioWebhookPayload.model_validate(payload_dict)

            # Process the message
            result = asyncio.run(process_message(payload))

            logger.info(f"Message {message_id} processed: {result['status']}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message {message_id}: {e}")
            # Don't retry malformed messages
            continue

        except Exception as e:
            logger.error(f"Failed to process message {message_id}: {e}", exc_info=True)
            # Add to batch failures for retry
            batch_item_failures.append({"itemIdentifier": message_id})

    # Return batch item failures for SQS to retry
    return {"batchItemFailures": batch_item_failures}
