import boto3
from typing import Optional
from voice_parser.core.config import S3Settings, get_s3_settings


class S3StorageService:
    def __init__(self, settings: Optional[S3Settings] = None):
        if settings is None:
            settings = get_s3_settings()
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        self.bucket_name = settings.s3_bucket_name

    async def upload_audio(self, audio_data: bytes, filename: str) -> str:
        key = f"voice-notes/{filename}"
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=audio_data,
            ContentType="audio/ogg",
        )
        return key

    async def download_audio(self, key: str) -> bytes:
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
        return response['Body'].read()


s3_service = S3StorageService()