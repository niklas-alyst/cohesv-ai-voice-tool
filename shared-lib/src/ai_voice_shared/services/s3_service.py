"""Unified S3 service for all AI Voice Tool microservices."""

import logging
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ai_voice_shared.models import (
    S3ListResponse,
    S3ObjectMetadata,
    S3ListIdsResponse,
    MessageIdSummary,
    MessageArtifactsResponse,
    MessageArtifact,
)
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
    ) -> S3ListResponse:
        """
        List objects in S3 bucket with pagination.

        Args:
            company_id: Company identifier for filtering
            message_intent: Message intent for filtering (job-to-be-done, knowledge-document, other)
            continuation_token: Token for pagination

        Returns:
            S3ListResponse containing:
                - files: List of S3ObjectMetadata (key, etag, size, last_modified)
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
                        S3ObjectMetadata(
                            key=obj["Key"],
                            etag=obj["ETag"],
                            size=obj["Size"],
                            last_modified=last_modified_str,
                        )
                    )

            result = S3ListResponse(
                files=files,
                nextContinuationToken=response.get("NextContinuationToken"),
            )

            logger.info(
                f"Listed {len(files)} objects, has more: {result.nextContinuationToken is not None}"
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

    async def list_objects_ids_only(
        self,
        company_id: str,
        message_intent: str,
        continuation_token: str | None = None,
    ) -> S3ListIdsResponse:
        """
        List message IDs with metadata for a company and intent.

        This method retrieves all files and groups them by message_id,
        returning only the message IDs with metadata instead of individual files.

        Args:
            company_id: Company identifier for filtering
            message_intent: Message intent for filtering (job-to-be-done, knowledge-document, other)
            continuation_token: Token for pagination

        Returns:
            S3ListIdsResponse containing:
                - message_ids: List of MessageIdSummary (message_id, tag, file_count)
                - nextContinuationToken: Token for next page (None if no more results)
        """
        # Get full file listing
        result = await self.list_objects(company_id, message_intent, continuation_token)

        # Group files by message_id
        message_groups: dict[str, dict[str, any]] = {}

        for file in result.files:
            # Parse the key: {company_id}/{message_intent}/{tag}_{message_id}_{file_type}.{extension}
            # Example: company123/job-to-be-done/bathroom-renovation_SM123456_audio.ogg
            key_parts = file.key.split("/")
            if len(key_parts) < 3:
                continue  # Skip malformed keys

            filename = key_parts[-1]  # e.g., bathroom-renovation_SM123456_audio.ogg

            # Find message_id by looking for pattern like _SM or _MM (Twilio message SIDs)
            # Split by underscores and look for the message ID pattern
            parts = filename.split("_")
            if len(parts) < 2:
                continue  # Skip malformed filenames

            # Message ID is typically the second-to-last part (before file_type)
            # Pattern: {tag}_{message_id}_{file_type}.{ext}
            # We need to find where the message ID starts
            # Twilio SIDs start with SM or MM followed by 32 hex chars
            message_id = None
            tag_parts = []

            for i, part in enumerate(parts):
                if part.startswith(("SM", "MM")) and len(part) >= 10:
                    # Found the message ID
                    message_id = part
                    tag_parts = parts[:i]
                    break

            if not message_id:
                continue  # Skip if we can't find a message ID

            tag = "_".join(tag_parts) if tag_parts else "unknown"

            # Add to groups
            if message_id not in message_groups:
                message_groups[message_id] = {
                    "message_id": message_id,
                    "tag": tag,
                    "file_count": 0,
                }

            message_groups[message_id]["file_count"] += 1

        # Convert to list of MessageIdSummary
        message_ids = [
            MessageIdSummary(**data) for data in message_groups.values()
        ]

        return S3ListIdsResponse(
            message_ids=message_ids,
            nextContinuationToken=result.nextContinuationToken,
        )

    async def list_files_by_message_id(
        self,
        company_id: str,
        message_id: str,
    ) -> MessageArtifactsResponse | None:
        """
        List all artifacts for a specific message.

        This method searches across all message intents to find artifacts
        for the specified message_id.

        Args:
            company_id: Company identifier
            message_id: Twilio message SID (e.g., SM123456...)

        Returns:
            MessageArtifactsResponse with all artifacts for the message,
            or None if no artifacts found

        Raises:
            ClientError: If S3 operation fails
        """
        # Search across all three intents
        all_intents = ["job-to-be-done", "knowledge-document", "other"]

        for intent in all_intents:
            prefix = f"{company_id}/{intent}/"

            try:
                # List all files for this company/intent combination
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=prefix,
                    MaxKeys=1000,
                )

                if "Contents" not in response:
                    continue  # No files for this intent

                # Filter files by message_id
                matching_files = []
                tag = None

                for obj in response["Contents"]:
                    key = obj["Key"]
                    filename = key.split("/")[-1]

                    # Check if this file belongs to our message_id
                    if f"_{message_id}_" in filename or filename.startswith(f"{message_id}_"):
                        # Determine file type
                        file_type = None
                        if filename.endswith("_audio.ogg"):
                            file_type = "audio"
                        elif filename.endswith("_full_text.txt"):
                            file_type = "full_text"
                        elif filename.endswith(".text_summary.txt"):
                            file_type = "text_summary"

                        if file_type:
                            # Extract tag from filename if we haven't yet
                            if tag is None:
                                # Parse tag from: {tag}_{message_id}_{file_type}.ext
                                parts = filename.split("_")
                                tag_parts = []
                                for i, part in enumerate(parts):
                                    if part.startswith(("SM", "MM")) and len(part) >= 10:
                                        tag_parts = parts[:i]
                                        break
                                tag = "_".join(tag_parts) if tag_parts else "unknown"

                            # Convert datetime to ISO 8601 string
                            last_modified = obj["LastModified"]
                            if isinstance(last_modified, datetime):
                                if last_modified.tzinfo is None:
                                    last_modified = last_modified.replace(tzinfo=timezone.utc)
                                last_modified_str = last_modified.isoformat()
                            else:
                                last_modified_str = str(last_modified)

                            matching_files.append(
                                MessageArtifact(
                                    key=key,
                                    type=file_type,
                                    etag=obj["ETag"],
                                    size=obj["Size"],
                                    last_modified=last_modified_str,
                                )
                            )

                # If we found files for this message, return them
                if matching_files:
                    logger.info(
                        f"Found {len(matching_files)} artifacts for message {message_id} "
                        f"in intent {intent}"
                    )

                    return MessageArtifactsResponse(
                        message_id=message_id,
                        company_id=company_id,
                        intent=intent,
                        tag=tag or "unknown",
                        files=matching_files,
                    )

            except ClientError as e:
                logger.error(f"Error searching intent {intent}: {e}")
                # Continue searching other intents
                continue

        # No files found for this message_id
        logger.warning(f"No artifacts found for message {message_id}")
        return None