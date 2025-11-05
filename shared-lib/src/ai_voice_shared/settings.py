"""Settings for AI Voice Tool shared services."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class CustomerLookupSettings(BaseSettings):
    """Settings for customer lookup service."""

    model_config = ConfigDict(env_file=".env", extra="ignore")

    customer_lookup_lambda_function_name: str
    aws_region: str


class S3Settings(BaseSettings):
    """Settings for S3 service."""

    model_config = ConfigDict(env_file=".env", extra="ignore")

    aws_region: str
    s3_bucket_name: str
    aws_profile: str | None = None
