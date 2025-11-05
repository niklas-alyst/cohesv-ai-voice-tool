"""Customer lookup service for fetching customer metadata."""

import aioboto3
import json
import logging
from typing import Optional

from ai_voice_shared.settings import CustomerLookupSettings
from ai_voice_shared.models import CustomerMetadata

logger = logging.getLogger(__name__)


class CustomerLookupClient:
    """Service for looking up customer metadata by phone number via AWS Lambda."""

    def __init__(self, settings: Optional[CustomerLookupSettings] = None):
        """
        Initialize the customer lookup service.

        Args:
            settings: Optional CustomerLookupSettings. If None, settings will be loaded from environment.
        """
        if settings is None:
            settings = CustomerLookupSettings()
        self.lambda_function_name = settings.customer_lookup_lambda_function_name
        self.aws_region = settings.aws_region

    async def fetch_customer_metadata(self, phone_number: str) -> CustomerMetadata:
        """
        Fetch customer metadata by phone number via AWS Lambda invocation.

        Args:
            phone_number: Phone number to lookup (with or without whatsapp: prefix)

        Returns:
            CustomerMetadata: Customer information including customer_id, company_id, and company_name

        Raises:
            ValueError: If the Lambda invocation fails or returns an error status
        """
        # Remove whatsapp: prefix if present
        clean_phone_number = phone_number.replace("whatsapp:", "")

        payload = {
            "phone_number": clean_phone_number
        }

        logger.info(f"Looking up customer metadata for phone number: {clean_phone_number}")

        try:
            # Use aioboto3 for async Lambda invocation
            session = aioboto3.Session()
            async with session.client('lambda', region_name=self.aws_region) as lambda_client:
                # Invoke Lambda function synchronously
                response = await lambda_client.invoke(
                    FunctionName=self.lambda_function_name,
                    InvocationType='RequestResponse',
                    Payload=json.dumps(payload)
                )

                # Parse response
                response_payload = await response['Payload'].read()
                response_data = json.loads(response_payload)

                # Check for Lambda errors
                if response.get('FunctionError'):
                    logger.error(f"Lambda function error: {response_data}")
                    raise ValueError(f"Lambda function error: {response_data}")

                # Parse status code from Lambda response
                status_code = response_data.get('statusCode', 500)
                body = json.loads(response_data.get('body', '{}'))

                if status_code == 404:
                    raise ValueError(f"Customer not found for phone number: {clean_phone_number}")
                elif status_code != 200:
                    raise ValueError(f"Lambda returned error status {status_code}: {body}")

                logger.info(f"Successfully retrieved customer metadata for {clean_phone_number}")

                # Validate response has required fields
                return CustomerMetadata.model_validate(body)

        except Exception as e:
            logger.error(f"Failed to fetch customer metadata: {e}")
            raise ValueError(f"Customer lookup failed: {e}")
