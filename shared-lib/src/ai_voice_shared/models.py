"""Shared data models for AI Voice Tool services."""

from pydantic import BaseModel


class CustomerMetadata(BaseModel):
    """Customer metadata returned from the customer lookup service."""

    customer_id: str
    company_id: str
    company_name: str
