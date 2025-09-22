from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class OpenAISettings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    openai_api_key: str


class S3Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    s3_bucket_name: str


class WhatsAppSettings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    whatsapp_access_token: str


def get_openai_settings() -> OpenAISettings:
    return OpenAISettings()


def get_s3_settings() -> S3Settings:
    return S3Settings()


def get_whatsapp_settings() -> WhatsAppSettings:
    return WhatsAppSettings()


