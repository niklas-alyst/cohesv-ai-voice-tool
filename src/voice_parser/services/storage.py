import boto3
from typing import Optional
from voice_parser.core.settings import S3Settings, get_s3_settings


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
        self.bucket_prefix = settings.s3_bucket_prefix

    async def upload_audio(self, audio_data: bytes, filename: str) -> str:
        key = f"{self.bucket_prefix}/voice-notes/{filename}"
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=audio_data,
            ContentType="audio/ogg",
        )
        return key

    async def download(self, key: str) -> bytes:
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
        return response['Body'].read()

    async def delete(self, key: str) -> None:
        self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)