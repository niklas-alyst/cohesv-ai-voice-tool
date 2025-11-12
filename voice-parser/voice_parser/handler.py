import asyncio
import json
import logging
from typing import List, Dict, Any
from ai_voice_shared.models import TwilioWebhookPayload
from .core.processor import process_message

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: object) -> Dict[str, Any]:
    """
    AWS Lambda handler for processing SQS messages.

    :param event: SQS event payload.
    :param context: Lambda context object.
    :return: A dict with a list of failed message IDs.
    """
    logger.info(f"Received SQS event with {len(event.get('Records', []))} records")

    # Use asyncio.run to manage the async loop
    results = asyncio.run(process_sqs_records(event.get("Records", [])))

    # Filter out failed items
    failed_items = [result for result in results if result["status"] == "failed"]
    logger.info(f"Processed {len(results)} messages, {len(failed_items)} failed")

    # Return batchItemFailures for SQS to retry
    return {
        "batchItemFailures": [
            {"itemIdentifier": item["message_id"]} for item in failed_items
        ]
    }


async def process_sqs_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Asynchronously processes a list of SQS records.

    :param records: A list of SQS records.
    :return: A list of processing results for each record.
    """
    tasks = []
    for record in records:
        tasks.append(process_single_record(record))

    # gather will run all tasks concurrently
    results = await asyncio.gather(*tasks)
    return results


async def process_single_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processes a single SQS record.

    :param record: The SQS record.
    :return: A dict with the processing result.
    """
    message_id = record.get("messageId")
    try:
        payload_body = json.loads(record.get("body", "{}"))
        webhook_payload = TwilioWebhookPayload(**payload_body)

        logger.info(f"Processing message: {webhook_payload.MessageSid}")
        result = await process_message(webhook_payload)

        return {
            "status": "success",
            "message_id": message_id,
            "result": result,
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error for messageId {message_id}: {e}")
        return {"status": "failed", "message_id": message_id, "error": str(e)}

    except Exception as e:
        # Catch-all for other unexpected errors
        logger.error(f"Unexpected error for messageId {message_id}: {e}", exc_info=True)
        return {"status": "failed", "message_id": message_id, "error": str(e)}
