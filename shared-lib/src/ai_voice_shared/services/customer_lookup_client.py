"""Customer lookup service for fetching customer metadata."""

import httpx
import logging
from typing import Optional

from pydantic import ValidationError

from ai_voice_shared.settings import CustomerLookupSettings
from ai_voice_shared.models import CustomerMetadata

logger = logging.getLogger(__name__)


class CustomerLookupClient:
    """Service for looking up customer metadata by phone number via HTTP API."""

    def __init__(self, settings: Optional[CustomerLookupSettings] = None):
        """
        Initialize the customer lookup service.

        Args:
            settings: Optional CustomerLookupSettings. If None, settings will be loaded from environment.
        """
        if settings is None:
            settings = CustomerLookupSettings()
        self.api_base_url = settings.wunse_api_base_url.rstrip('/')
        self.api_key = settings.wunse_api_key

    async def fetch_customer_metadata(self, phone_number: str) -> CustomerMetadata:
        """
        Fetch customer metadata by phone number via HTTP API.

        Args:
            phone_number: Phone number to lookup (with or without whatsapp: prefix)

        Returns:
            CustomerMetadata: Customer information including customer_id, company_id, and company_name

        Raises:
            ValueError: If the API request fails or returns an error status
        """
        # Remove whatsapp: prefix if present
        clean_phone_number = phone_number.replace("whatsapp:", "")

        logger.info(f"Looking up customer metadata for phone number: {clean_phone_number}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/customer-lookup/customers/lookup",
                    params={"phone_number": clean_phone_number},
                    headers={"x-api-key": self.api_key},
                    timeout=10.0
                )

                # Handle different status codes
                if response.status_code == 404:
                    error_body = response.json()
                    error_msg = error_body.get('error', f'Customer not found for phone number: {clean_phone_number}')
                    logger.warning(f"Customer not found: {error_msg}")
                    raise ValueError(error_msg)
                elif response.status_code == 401:
                    logger.error("Unauthorized: Invalid API key")
                    raise ValueError("Customer lookup failed: Unauthorized")
                elif response.status_code == 400:
                    error_body = response.json()
                    error_msg = error_body.get('error', 'Bad request')
                    logger.error(f"Bad request: {error_msg}")
                    raise ValueError(f"Customer lookup failed: {error_msg}")
                elif response.status_code != 200:
                    logger.error(f"API returned error status {response.status_code}")
                    raise ValueError(f"Customer lookup failed: HTTP {response.status_code}")

                # Parse and validate response
                response.raise_for_status()
                body = response.json()

                logger.info(f"Successfully retrieved customer metadata for {clean_phone_number}")

                # Validate response has required fields
                return CustomerMetadata.model_validate(body)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during customer lookup: {e}")
            raise ValueError(f"Customer lookup failed: {e}")
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch customer metadata: {e}")
            raise ValueError(f"Customer lookup failed: {e}")
