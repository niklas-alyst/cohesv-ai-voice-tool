from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from typing import Optional

class OpenAISettings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")
    openai_api_key: str


class S3Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    aws_region: str
    s3_bucket_name: str
    s3_bucket_prefix: str
    aws_profile: Optional[str]


class WhatsAppSettings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    whatsapp_access_token: str
    whatsapp_business_phone_number_id: str  # Our business phone number ID (sender)