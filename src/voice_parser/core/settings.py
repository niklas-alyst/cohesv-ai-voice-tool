from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class OpenAISettings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str


class S3Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    aws_region: str = "eu-north-1"
    s3_bucket_name: str
    s3_bucket_prefix: str


class WhatsAppSettings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    whatsapp_access_token: str
    whatsapp_business_phone_number_id: str  # Our business phone number ID (sender)