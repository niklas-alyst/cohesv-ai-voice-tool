"""Data repository for customer lookup."""

import json
import logging
from typing import Optional, Dict, Any, List
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class CustomerRepository:
    """Repository for customer data lookup."""

    def __init__(self, s3_bucket: str = "cohesv-ai-voice-tool", s3_key: str = "customers.json"):
        """Initialize the customer repository.

        Args:
            s3_bucket: S3 bucket name containing the customers data
            s3_key: S3 key (path) to the customers.json file
        """
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        self.s3_client = boto3.client("s3")
        self._customers: Optional[List[Dict[str, Any]]] = None
        logger.info(f"CustomerRepository initialized with S3 source: s3://{s3_bucket}/{s3_key}")

    def _load_customers(self) -> List[Dict[str, Any]]:
        """Load customers data from S3.

        Returns:
            List of customer dictionaries

        Raises:
            ClientError: If S3 access fails
        """
        if self._customers is not None:
            return self._customers

        try:
            logger.info(f"Loading customers from S3: s3://{self.s3_bucket}/{self.s3_key}")
            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=self.s3_key)
            data = response["Body"].read().decode("utf-8")
            self._customers = json.loads(data)
            logger.info(f"Loaded {len(self._customers)} customers from S3")
            return self._customers
        except ClientError as e:
            logger.error(f"Failed to load customers from S3: {e}")
            raise

    def find_by_phone_number(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Find customer by phone number.

        Args:
            phone_number: Phone number to search for (cleaned, without whatsapp: prefix)

        Returns:
            Customer data dict with customer_id, company_id, company_name, or None if not found
        """
        logger.info(f"Looking up customer by phone number: {phone_number}")

        customers = self._load_customers()
        for customer in customers:
            if customer["phone_number"] == phone_number:
                logger.info(f"Customer found: {customer['customer_id']}")
                return {
                    "customer_id": customer["customer_id"],
                    "company_id": customer["company_id"],
                    "company_name": customer["company_name"]
                }

        logger.warning(f"No customer found for phone number: {phone_number}")
        return None
