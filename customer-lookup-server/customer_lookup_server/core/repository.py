"""Data repository for customer lookup."""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class CustomerRepository:
    """Repository for customer data lookup."""

    # Hardcoded dummy data - will be replaced with database queries later
    CUSTOMERS = [
        {
            "phone_number": "+61400000000",
            "customer_id": "cust_dummy_001",
            "company_id": "comp_dummy_001",
            "company_name": "Dummy Test Company"
        },
        # Add more dummy customers here as needed
    ]

    def __init__(self):
        """Initialize the customer repository."""
        logger.info("CustomerRepository initialized with hardcoded data")

    def find_by_phone_number(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Find customer by phone number.

        Args:
            phone_number: Phone number to search for (cleaned, without whatsapp: prefix)

        Returns:
            Customer data dict with customer_id, company_id, company_name, or None if not found
        """
        logger.info(f"Looking up customer by phone number: {phone_number}")

        for customer in self.CUSTOMERS:
            if customer["phone_number"] == phone_number:
                logger.info(f"Customer found: {customer['customer_id']}")
                return {
                    "customer_id": customer["customer_id"],
                    "company_id": customer["company_id"],
                    "company_name": customer["company_name"]
                }

        logger.warning(f"No customer found for phone number: {phone_number}")
        return None
