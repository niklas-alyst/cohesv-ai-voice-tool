import logging
import boto3
from typing import Optional
from voice_parser.core.settings import S3Settings

logger = logging.getLogger(__name__)


class S3StorageService:
    def __init__(self, settings: Optional[S3Settings] = None):
        if settings is None:
            settings = S3Settings()

        self._session = boto3.Session(
            profile_name=settings.aws_profile
        )
        self.s3_client = self._session.client(
            "s3",
            region_name=settings.aws_region,
        )
        self.bucket_name = settings.s3_bucket_name
        self.bucket_prefix = settings.s3_bucket_prefix

    async def exists(self, key: str) -> bool:
        """Check if an object exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            logger.debug(f"Object exists in S3: {key}")
            return True
        except self.s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.debug(f"Object does not exist in S3: {key}")
                return False
            else:
                logger.error(f"Error checking if object exists in S3: {key}", exc_info=True)
                raise

    async def upload_audio(self, audio_data: bytes, filename: str, overwrite: bool = False) -> str:
        """Upload audio file to S3.

        Args:
            audio_data: Audio file bytes
            filename: Name of the file
            overwrite: Whether to overwrite existing file (default: False)

        Returns:
            S3 key of the uploaded file

        Raises:
            FileExistsError: If file exists and overwrite is False
        """
        key = f"{self.bucket_prefix}/voice-notes/{filename}"

        # Check if file exists and handle overwrite
        if await self.exists(key):
            if not overwrite:
                logger.warning(f"Audio file already exists and overwrite is False: {key}")
                raise FileExistsError(f"File already exists at {key}. Set overwrite=True to replace it.")
            logger.info(f"Overwriting existing audio file: {key}")
        else:
            logger.info(f"Uploading new audio file: {key}")

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=audio_data,
            ContentType="audio/ogg",
        )
        logger.info(f"Successfully uploaded audio file: {key}")
        return key
    
    async def upload_text(self, text_data: str, filename: str, overwrite: bool = False) -> str:
        """Save text file to S3.

        Args:
            text_data: Text content to save
            filename: Name of the file
            overwrite: Whether to overwrite existing file (default: False)

        Returns:
            S3 key of the saved file

        Raises:
            FileExistsError: If file exists and overwrite is False
        """
        key = f"{self.bucket_prefix}/voice-notes/{filename}"

        # Check if file exists and handle overwrite
        if await self.exists(key):
            if not overwrite:
                logger.warning(f"Text file already exists and overwrite is False: {key}")
                raise FileExistsError(f"File already exists at {key}. Set overwrite=True to replace it.")
            logger.info(f"Overwriting existing text file: {key}")
        else:
            logger.info(f"Saving new text file: {key}")

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=text_data.encode('utf-8'),
            ContentType="text/plain",
        )
        logger.info(f"Successfully saved text file: {key}")
        return key

    async def download(self, key: str) -> bytes:
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
        return response['Body'].read()

    async def delete(self, key: str) -> None:
        self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
