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
    aws_profile: Optional[str] = None


class TwilioWhatsAppSettings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str  # Format: "whatsapp:+14155238886"