from pydantic_settings import BaseSettings


class OpenAISettings(BaseSettings):
    openai_api_key: str
    whisper_api_key: str

    class Config:
        env_file = ".env"


class S3Settings(BaseSettings):
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    s3_bucket_name: str

    class Config:
        env_file = ".env"


class WhatsAppSettings(BaseSettings):
    whatsapp_access_token: str

    class Config:
        env_file = ".env"


def get_openai_settings() -> OpenAISettings:
    return OpenAISettings()


def get_s3_settings() -> S3Settings:
    return S3Settings()


def get_whatsapp_settings() -> WhatsAppSettings:
    return WhatsAppSettings()


