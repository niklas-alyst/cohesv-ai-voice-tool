"""Settings for Data API Server."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(env_file=".env", extra="ignore")

    # AWS Configuration
    aws_region: str = "ap-southeast-2"  # Default region, Lambda provides AWS_REGION automatically
    s3_bucket_name: str
    aws_profile: str | None = None

    # API Gateway configuration
    environment: str = "dev"  # Environment name used as API Gateway stage

    # API Gateway will handle API key validation, but we include this for local testing
    api_key: str | None = None
