import pytest
import os
from pathlib import Path
from dotenv import load_dotenv
from voice_parser.services.storage import S3StorageService
from voice_parser.core.settings import S3Settings


@pytest.fixture(scope="session", autouse=True)
def load_test_env():
    """Load test environment variables from .env.test"""
    load_dotenv(".env.test")


@pytest.fixture
def test_s3_settings():
    """Create S3 settings using test environment variables"""
    return S3Settings(
        aws_region=os.getenv("AWS_REGION"),
        s3_bucket_name=os.getenv("S3_BUCKET_NAME"),
        s3_bucket_prefix=os.getenv("S3_BUCKET_PREFIX"),
    )


@pytest.fixture
def storage_service(test_s3_settings):
    """Create storage service with test settings"""
    return S3StorageService(settings=test_s3_settings)


@pytest.fixture
def test_audio_file():
    """Provide path to test audio file"""
    test_dir = Path(__file__).parent.parent
    audio_file = test_dir / "fixtures" / "test_audio.ogg"

    if not audio_file.exists():
        pytest.skip(f"Test audio file not found: {audio_file}")

    return audio_file


class TestS3StorageServiceIntegration:
    """Integration tests for S3 storage service using real AWS S3"""

    @pytest.mark.asyncio
    async def test_upload_download_delete_audio_file(self, storage_service, test_audio_file):
        """Test uploading, downloading, and deleting an audio file"""
        # Read the test audio file
        with open(test_audio_file, "rb") as f:
            original_audio_data = f.read()

        test_filename = f"test_{test_audio_file.name}"
        uploaded_key = None

        try:
            # Upload the audio file
            uploaded_key = await storage_service.upload_audio(
                audio_data=original_audio_data,
                filename=test_filename
            )

            # Verify the key format
            assert uploaded_key.endswith(f"/voice-notes/{test_filename}")
            assert uploaded_key.startswith(storage_service.bucket_prefix)

            # Download the audio file
            downloaded_audio_data = await storage_service.download(uploaded_key)

            # Verify the downloaded data matches the original
            assert downloaded_audio_data == original_audio_data
            assert len(downloaded_audio_data) > 0

        finally:
            # Clean up: delete the uploaded file
            if uploaded_key:
                await storage_service.delete(uploaded_key)

    @pytest.mark.asyncio
    async def test_download_nonexistent_file_fails(self, storage_service):
        """Test that downloading a non-existent file raises an appropriate error"""
        nonexistent_key = f"{storage_service.bucket_prefix}/voice-notes/nonexistent.ogg"

        with pytest.raises(Exception):  # S3 will raise an error for missing files
            await storage_service.download(nonexistent_key)