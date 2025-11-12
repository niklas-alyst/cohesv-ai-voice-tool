"""End-to-end tests for S3 service against real AWS S3."""

import os

import pytest
from dotenv import load_dotenv

from ai_voice_shared.models import S3ListResponse, S3ObjectMetadata
from ai_voice_shared.services.s3_service import S3Service
from ai_voice_shared.settings import S3Settings


@pytest.fixture(scope="session", autouse=True)
def load_test_env():
    """Load test environment variables from .env.test"""
    load_dotenv(".env.test")


@pytest.fixture
def test_s3_settings():
    """Create S3 settings using test environment variables"""
    # Get required values from environment
    aws_region = os.getenv("AWS_REGION")
    s3_bucket_name = os.getenv("S3_BUCKET_NAME")
    aws_profile = os.getenv("AWS_PROFILE")

    # Validate required settings are present
    if not aws_region:
        pytest.skip("AWS_REGION not set in environment")
    if not s3_bucket_name:
        pytest.skip("S3_BUCKET_NAME not set in environment")

    return S3Settings(
        aws_region=aws_region,
        s3_bucket_name=s3_bucket_name,
        aws_profile=aws_profile,
    )


@pytest.fixture
def s3_service(test_s3_settings):
    """Create S3 service with test settings"""
    return S3Service(settings=test_s3_settings)


@pytest.fixture
def test_audio_data():
    """Provide test audio data"""
    # Create a simple test audio file (just some bytes for testing)
    return b"fake audio data for testing purposes"


@pytest.fixture
def test_text_data():
    """Provide test text data"""
    return "This is test text content"


@pytest.mark.e2e
class TestS3Service:
    """End-to-end tests for S3 service against real AWS S3"""

    @pytest.mark.asyncio
    async def test_upload_download_delete_audio(self, s3_service, test_audio_data):
        """Test uploading, downloading, and deleting an audio file"""
        test_key = "test/audio/test_file.ogg"
        uploaded_key = None

        try:
            # Upload the audio file
            uploaded_key = await s3_service.upload(
                data=test_audio_data,
                key=test_key,
                content_type="audio/ogg",
                overwrite=False,
            )

            # Verify the key matches what we provided
            assert uploaded_key == test_key

            # Verify file exists
            exists = await s3_service.exists(test_key)
            assert exists is True

            # Download the audio file
            downloaded_data = await s3_service.download(test_key)

            # Verify the downloaded data matches the original
            assert downloaded_data == test_audio_data

        finally:
            # Clean up: delete the uploaded file
            if uploaded_key:
                await s3_service.delete(uploaded_key)

                # Verify file no longer exists
                exists = await s3_service.exists(test_key)
                assert exists is False

    @pytest.mark.asyncio
    async def test_upload_text_file(self, s3_service, test_text_data):
        """Test uploading and downloading a text file"""
        test_key = "test/text/test_file.txt"
        uploaded_key = None

        try:
            # Upload the text file
            uploaded_key = await s3_service.upload(
                data=test_text_data.encode("utf-8"),
                key=test_key,
                content_type="text/plain",
                overwrite=False,
            )

            # Download the text file
            downloaded_data = await s3_service.download(test_key)

            # Verify the downloaded data matches the original
            assert downloaded_data.decode("utf-8") == test_text_data

        finally:
            # Clean up
            if uploaded_key:
                await s3_service.delete(uploaded_key)

    @pytest.mark.asyncio
    async def test_upload_overwrite_protection(self, s3_service, test_audio_data):
        """Test that overwrite protection prevents accidental overwrites"""
        test_key = "test/overwrite/test_file.ogg"

        try:
            # Upload file first time
            await s3_service.upload(
                data=test_audio_data,
                key=test_key,
                content_type="audio/ogg",
                overwrite=False,
            )

            # Try to upload again without overwrite flag - should raise error
            with pytest.raises(FileExistsError) as exc_info:
                await s3_service.upload(
                    data=test_audio_data,
                    key=test_key,
                    content_type="audio/ogg",
                    overwrite=False,
                )

            assert "already exists" in str(exc_info.value)

            # Upload with overwrite=True should succeed
            await s3_service.upload(
                data=b"new data",
                key=test_key,
                content_type="audio/ogg",
                overwrite=True,
            )

            # Verify new data was uploaded
            downloaded = await s3_service.download(test_key)
            assert downloaded == b"new data"

        finally:
            # Clean up
            await s3_service.delete(test_key)

    @pytest.mark.asyncio
    async def test_exists_for_nonexistent_file(self, s3_service):
        """Test that exists() returns False for non-existent file"""
        nonexistent_key = "test/nonexistent/file.ogg"

        exists = await s3_service.exists(nonexistent_key)
        assert exists is False

    @pytest.mark.asyncio
    async def test_download_nonexistent_file_fails(self, s3_service):
        """Test that downloading a non-existent file raises an appropriate error"""
        nonexistent_key = "test/nonexistent/file.ogg"

        with pytest.raises(Exception):  # S3 will raise ClientError for missing files
            await s3_service.download(nonexistent_key)

    @pytest.mark.asyncio
    async def test_list_objects(self, s3_service, test_audio_data):
        """Test listing objects with prefix filtering and pagination"""
        # Create test files
        company_id = "test_company"
        message_intent = "test_intent"
        test_keys = [
            f"{company_id}/{message_intent}/file1.ogg",
            f"{company_id}/{message_intent}/file2.ogg",
            f"{company_id}/{message_intent}/file3.txt",
        ]

        try:
            # Upload test files
            for key in test_keys:
                await s3_service.upload(
                    data=test_audio_data,
                    key=key,
                    content_type="audio/ogg",
                    overwrite=False,
                )

            # List objects
            result = await s3_service.list_objects(
                company_id=company_id,
                message_intent=message_intent,
                continuation_token=None,
            )

            # Verify result is proper Pydantic model
            assert isinstance(result, S3ListResponse)
            assert len(result.files) == 3
            assert result.nextContinuationToken is None or isinstance(
                result.nextContinuationToken, str
            )

            # Verify file metadata structure and types
            for file_info in result.files:
                assert isinstance(file_info, S3ObjectMetadata)
                assert isinstance(file_info.key, str)
                assert isinstance(file_info.etag, str)
                assert isinstance(file_info.size, int)
                assert isinstance(file_info.last_modified, str)
                assert file_info.key in test_keys

        finally:
            # Clean up
            for key in test_keys:
                await s3_service.delete(key)

    @pytest.mark.asyncio
    async def test_generate_presigned_url(self, s3_service, test_audio_data):
        """Test generating presigned URLs for existing objects"""
        test_key = "test/presigned/test_file.ogg"

        try:
            # Upload test file
            await s3_service.upload(
                data=test_audio_data,
                key=test_key,
                content_type="audio/ogg",
                overwrite=False,
            )

            # Generate presigned URL
            url = await s3_service.generate_presigned_url(
                key=test_key, expiration=300
            )

            # Verify URL is a string and contains expected elements
            assert isinstance(url, str)
            assert "https://" in url
            assert s3_service.bucket_name in url
            assert test_key in url

        finally:
            # Clean up
            await s3_service.delete(test_key)

    @pytest.mark.asyncio
    async def test_generate_presigned_url_for_nonexistent_file(self, s3_service):
        """Test that generating presigned URL for non-existent file raises ValueError"""
        nonexistent_key = "test/nonexistent/file.ogg"

        with pytest.raises(ValueError) as exc_info:
            await s3_service.generate_presigned_url(key=nonexistent_key)

        assert "not found" in str(exc_info.value).lower()
