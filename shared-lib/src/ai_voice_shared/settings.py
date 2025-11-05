"""Settings for AI Voice Tool shared services."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class CustomerLookupSettings(BaseSettings):
    """Settings for customer lookup service."""

    model_config = ConfigDict(env_file=".env", extra="ignore")

    customer_lookup_url: str
    customer_lookup_api_key: str
