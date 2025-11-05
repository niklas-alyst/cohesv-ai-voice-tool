"""Unified S3 service for all AI Voice Tool microservices."""

import logging
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ai_voice_shared.settings import S3Settings

logger = logging.getLogger(__name__)


class S3Service:
    """
    Unified S3 service supporting both read/write operations and listing/presigned URLs.

    This service combines capabilities from the voice-parser storage service
    and the data-api-server S3 service.
    """

    def __init__(self, settings: S3Settings | None = None):
        """
        Initialize S3 service with settings.

        Args:
            settings: S3 settings. If None, will be loaded from environment.
        """
        if settings is None:
            settings = S3Settings()

        self.settings = settings
        self.bucket_name = settings.s3_bucket_name

        # Configure boto3 session and client
        session_kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if settings.aws_profile:
            session_kwargs["profile_name"] = settings.aws_profile

        session = boto3.Session(**session_kwargs)
        config = Config(region_name=settings.aws_region)
        self.s3_client = session.client("s3", config=config)

    async def exists(self, key: str) -> bool:
        """
        Check if an object exists in S3.

        Args:
            key: S3 object key

        Returns:
            True if object exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            logger.debug(f"Object exists in S3: {key}")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logger.debug(f"Object does not exist in S3: {key}")
                return False
            else:
                logger.error(f"Error checking if object exists in S3: {key}", exc_info=True)
                raise

    async def upload(
        self,
        data: bytes,
        key: str,
        content_type: str,
        overwrite: bool = False,
    ) -> str:
        """
        Upload data to S3.

        Args:
            data: Data to upload as bytes
            key: S3 object key
            content_type: Content type (e.g., "audio/ogg", "text/plain")
            overwrite: Whether to overwrite existing file (default: False)

        Returns:
            S3 key of the uploaded file

        Raises:
            FileExistsError: If file exists and overwrite is False
        """
        # Check if file exists and handle overwrite
        if await self.exists(key):
            if not overwrite:
                logger.warning(f"File already exists and overwrite is False: {key}")
                raise FileExistsError(
                    f"File already exists at {key}. Set overwrite=True to replace it."
                )
            logger.info(f"Overwriting existing file: {key}")
        else:
            logger.info(f"Uploading new file: {key}")

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        logger.info(f"Successfully uploaded file: {key}")
        return key

    async def download(self, key: str) -> bytes:
        """
        Download an object from S3.

        Args:
            key: S3 object key

        Returns:
            Object data as bytes

        Raises:
            ClientError: If object doesn't exist or other S3 error occurs
        """
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
        return response["Body"].read()

    async def delete(self, key: str) -> None:
        """
        Delete an object from S3.

        Args:
            key: S3 object key
        """
        self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
        logger.info(f"Deleted object from S3: {key}")

    async def list_objects(
        self,
        company_id: str,
        message_intent: str,
        continuation_token: str | None = None,
    ) -> dict[str, Any]:
        """
        List objects in S3 bucket with pagination.

        Args:
            company_id: Company identifier for filtering
            message_intent: Message intent for filtering (job-to-be-done, knowledge-document, other)
            continuation_token: Token for pagination

        Returns:
            Dictionary containing:
                - files: List of file metadata dicts (key, etag, size, last_modified)
                - nextContinuationToken: Token for next page (None if no more results)
        """
        # Construct prefix based on company_id and message_intent
        prefix = f"{company_id}/{message_intent}/"

        logger.info(f"Listing objects with prefix: {prefix}")

        try:
            params = {
                "Bucket": self.bucket_name,
                "Prefix": prefix,
                "MaxKeys": 1000,  # Max allowed by S3
            }

            if continuation_token:
                params["ContinuationToken"] = continuation_token

            response = self.s3_client.list_objects_v2(**params)

            files = []
            if "Contents" in response:
                for obj in response["Contents"]:
                    # Convert datetime to ISO 8601 string
                    last_modified = obj["LastModified"]
                    if isinstance(last_modified, datetime):
                        # Ensure timezone-aware datetime in UTC
                        if last_modified.tzinfo is None:
                            last_modified = last_modified.replace(tzinfo=timezone.utc)
                        last_modified_str = last_modified.isoformat()
                    else:
                        last_modified_str = str(last_modified)

                    files.append(
                        {
                            "key": obj["Key"],
                            "etag": obj["ETag"],
                            "size": obj["Size"],
                            "last_modified": last_modified_str,
                        }
                    )

            result = {
                "files": files,
                "nextContinuationToken": response.get("NextContinuationToken"),
            }

            logger.info(
                f"Listed {len(files)} objects, has more: {result['nextContinuationToken'] is not None}"
            )

            return result

        except ClientError as e:
            logger.error(f"Error listing objects: {e}")
            raise

    async def generate_presigned_url(self, key: str, expiration: int = 300) -> str:
        """
        Generate a presigned URL for downloading an object.

        Args:
            key: S3 object key
            expiration: URL expiration time in seconds (default: 300 = 5 minutes)

        Returns:
            Presigned URL string

        Raises:
            ValueError: If object does not exist
        """
        # First check if object exists
        if not await self.exists(key):
            raise ValueError(f"Object not found: {key}")

        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expiration,
            )
            logger.info(f"Generated presigned URL for: {key}")
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise