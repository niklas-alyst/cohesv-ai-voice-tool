
import pytest
import json
from unittest.mock import patch, MagicMock
from voice_parser.handler import handler
from voice_parser.core.processor import ProcessorException


@pytest.fixture
def mock_process_message():
    """Fixture to mock the core process_message function."""
    with patch("voice_parser.handler.process_message", autospec=True) as mock:
        yield mock


def create_sqs_event(records_data: list) -> dict:
    """Helper to create an SQS event dictionary."""
    records = []
    for i, data in enumerate(records_data):
        records.append(
            {
                "messageId": f"msg-id-{i}",
                "receiptHandle": f"receipt-handle-{i}",
                "body": json.dumps(data),
                "attributes": {},
                "messageAttributes": {},
                "md5OfBody": "...",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:MyQueue",
                "awsRegion": "us-east-1",
            }
        )
    return {"Records": records}


@pytest.mark.unit
def test_handler_partial_batch_failure(mock_process_message):
    """
    Test that the handler correctly returns failed message IDs for partial failures.
    """
    # Arrange
    # Mock two successful messages and one failed message
    success_payload_1 = {"MessageSid": "sid-success-1", "From": "111"}
    failure_payload = {"MessageSid": "sid-failure-1", "From": "222"}
    success_payload_2 = {"MessageSid": "sid-success-2", "From": "333"}

    sqs_event = create_sqs_event(
        [success_payload_1, failure_payload, success_payload_2]
    )

    # The processor should succeed for the first and third, and raise an exception for the second
    mock_process_message.side_effect = [
        {"status": "success", "message_id": "sid-success-1"},
        ProcessorException("Something went wrong"),
        {"status": "success", "message_id": "sid-success-2"},
    ]

    # Act
    result = handler(sqs_event, {})

    # Assert
    # The handler should return a list containing only the ID of the failed message
    assert "batchItemFailures" in result
    failures = result["batchItemFailures"]
    assert len(failures) == 1
    assert failures[0]["itemIdentifier"] == "msg-id-1"  # The messageId of the failed record

    # Verify process_message was called for all three records
    assert mock_process_message.call_count == 3

