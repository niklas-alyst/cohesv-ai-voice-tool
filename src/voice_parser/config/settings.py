from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    whatsapp_access_token: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    s3_bucket_name: str
    whisper_api_key: str
    openai_api_key: str

    class Config:
        env_file = ".env"


settings = Settings()