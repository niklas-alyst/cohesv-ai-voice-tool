"""Customer lookup service for fetching customer metadata."""

import httpx
import logging
from typing import Optional

from ai_voice_shared.settings import CustomerLookupSettings
from ai_voice_shared.models import CustomerMetadata

logger = logging.getLogger(__name__)


class CustomerLookupClient:
    """Service for looking up customer metadata by phone number."""

    def __init__(self, settings: Optional[CustomerLookupSettings] = None):
        """
        Initialize the customer lookup service.

        Args:
            settings: Optional CustomerLookupSettings. If None, settings will be loaded from environment.
        """
        if settings is None:
            settings = CustomerLookupSettings()
        self.lookup_url = settings.customer_lookup_url
        self.api_key = settings.customer_lookup_api_key

    async def fetch_customer_metadata(self, phone_number: str) -> CustomerMetadata:
        """
        Fetch customer metadata by phone number.

        Uses POST request for security (phone numbers are sensitive data and
        should not appear in URL logs).

        Args:
            phone_number: Phone number to lookup (with or without whatsapp: prefix)

        Returns:
            CustomerMetadata: Customer information including customer_id, company_id, and company_name

        Raises:
            httpx.HTTPStatusError: If the API request fails
            ValueError: If the response is missing required fields
        """
        # Remove whatsapp: prefix if present
        clean_phone_number = phone_number.replace("whatsapp:", "")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "phone_number": clean_phone_number
        }

        logger.info(f"Looking up customer metadata for phone number: {clean_phone_number}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.lookup_url,
                json=payload,
                headers=headers,
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

        logger.info(f"Successfully retrieved customer metadata for {clean_phone_number}")

        # Validate response has required fields
        try:
            return CustomerMetadata.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to parse customer metadata response: {e}")
            raise ValueError(f"Invalid customer metadata response: {e}")
