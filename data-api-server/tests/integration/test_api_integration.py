import os
from unittest.mock import patch

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

# Removed: from data_api_server.main import app



@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    # S3_BUCKET_NAME will be set in the client fixture before app import


@pytest.fixture(scope="function")
def s3_client(aws_credentials):
    """Mocked S3 client."""
    with mock_aws():
        yield boto3.client("s3", region_name="us-east-1")


@pytest.fixture(scope="function")
def test_bucket_name():
    """Return a test S3 bucket name."""
    return "test-data-api-bucket"


@pytest.fixture(scope="function")
def setup_s3_bucket(s3_client, test_bucket_name):
    """Create a mocked S3 bucket and upload test files."""
    s3_client.create_bucket(Bucket=test_bucket_name)

    # Test files for company123, job-to-be-done
    s3_client.put_object(
        Bucket=test_bucket_name,
        Key="company123/job-to-be-done/task1_SM1_audio.ogg",
        Body=b"audio_content_1",
    )
    s3_client.put_object(
        Bucket=test_bucket_name,
        Key="company123/job-to-be-done/task1_SM1_full_text.txt",
        Body=b"text_content_1",
    )
    s3_client.put_object(
        Bucket=test_bucket_name,
        Key="company123/job-to-be-done/task2_SM2_audio.ogg",
        Body=b"audio_content_2",
    )

    # Test files for company123, knowledge-document
    s3_client.put_object(
        Bucket=test_bucket_name,
        Key="company123/knowledge-document/doc1_SM3_full_text.txt",
        Body=b"doc_content_1",
    )

    # Test files for another_company, job-to-be-done
    s3_client.put_object(
        Bucket=test_bucket_name,
        Key="another_company/job-to-be-done/taskA_SM4_audio.ogg",
        Body=b"audio_content_A",
    )

    yield
    # Moto handles cleanup automatically


@pytest.fixture(scope="function")
def client(test_bucket_name, s3_client): # Add s3_client here
    """Create a TestClient for the FastAPI app with mocked settings."""
    # Set environment variables before importing app
    os.environ["S3_BUCKET_NAME"] = test_bucket_name
    os.environ["API_KEY"] = ""  # Disable API key for integration tests

    # Import app here to ensure settings are loaded with mocked env vars
    from data_api_server.main import app
    from ai_voice_shared.services.s3_service import S3Service
    from ai_voice_shared.settings import S3Settings

    # Create S3Settings for the mocked S3Service
    mock_s3_settings = S3Settings(
        aws_region="us-east-1",
        s3_bucket_name=test_bucket_name,
        aws_profile=None, # No profile needed for moto
    )

    # Create a mocked S3Service instance that uses the moto-patched s3_client
    mock_s3_service_instance = S3Service(mock_s3_settings)
    mock_s3_service_instance.s3_client = s3_client # Inject the moto-patched client

    with patch("data_api_server.main.s3_service", new=mock_s3_service_instance):
        yield TestClient(app)


class TestIntegrationListFiles:
    """Integration tests for the /files/list endpoint."""

    def test_list_files_success(self, client, setup_s3_bucket):
        """Test successful listing of files for a given company and intent."""
        response = client.get(
            "/files/list",
            params={"company_id": "company123", "message_intent": "job-to-be-done"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) == 3
        assert any(
            f["key"] == "company123/job-to-be-done/task1_SM1_audio.ogg"
            for f in data["files"]
        )
        assert any(
            f["key"] == "company123/job-to-be-done/task1_SM1_full_text.txt"
            for f in data["files"]
        )
        assert any(
            f["key"] == "company123/job-to-be-done/task2_SM2_audio.ogg"
            for f in data["files"]
        )
        assert data["nextContinuationToken"] is None

    def test_list_files_empty_result(self, client, setup_s3_bucket):
        """Test listing files for a company/intent with no matching files."""
        response = client.get(
            "/files/list",
            params={"company_id": "company123", "message_intent": "other"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) == 0
        assert data["nextContinuationToken"] is None

    def test_list_files_another_company(self, client, setup_s3_bucket):
        """Test listing files for a different company."""
        response = client.get(
            "/files/list",
            params={"company_id": "another_company", "message_intent": "job-to-be-done"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) == 1
        assert data["files"][0]["key"] == "another_company/job-to-be-done/taskA_SM4_audio.ogg"


class TestIntegrationGetDownloadUrl:
    """Integration tests for the /files/get-download-url endpoint."""

    def test_get_download_url_success(self, client, setup_s3_bucket):
        """Test successful generation of a presigned URL for an existing file."""
        file_key = "company123/job-to-be-done/task1_SM1_audio.ogg"
        response = client.get(
            "/files/get-download-url", params={"key": file_key}
        )

        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert file_key in data["url"]
        assert "Signature" in data["url"]  # Check for presigned URL component

    def test_get_download_url_file_not_found(self, client, setup_s3_bucket):
        """Test that requesting a URL for a non-existent file returns 404."""
        non_existent_key = "company123/job-to-be-done/non_existent_file.ogg"
        response = client.get(
            "/files/get-download-url", params={"key": non_existent_key}
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "File not found"

    def test_get_download_url_invalid_key_format(self, client, setup_s3_bucket):
        """Test that an invalid key format (e.g., not URL-encoded) is handled."""
        # This test primarily checks that the S3 service correctly handles the key it receives.
        # FastAPI automatically URL-decodes query parameters, so we pass a "valid" key string.
        # The S3 client will then determine if it exists.
        invalid_key = "company123/job-to-be-done/task1_SM1_audio.ogg/extra" # Not a valid S3 key
        response = client.get(
            "/files/get-download-url", params={"key": invalid_key}
        )
        # Moto's S3 client might return 404 for non-existent keys, which is what we expect.
        assert response.status_code == 404
        assert response.json()["detail"] == "File not found"


class TestIntegrationListFilesWithOutputFormat:
    """Integration tests for the /files/list endpoint with output_format."""

    def test_list_files_ids_format(self, client, setup_s3_bucket):
        """Test listing files with output_format=ids."""
        response = client.get(
            "/files/list",
            params={
                "company_id": "company123",
                "message_intent": "job-to-be-done",
                "output_format": "ids",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "message_ids" in data
        assert len(data["message_ids"]) == 2  # SM1 and SM2

        # Check message IDs are present
        message_ids = [msg["message_id"] for msg in data["message_ids"]]
        assert "SM1" in message_ids
        assert "SM2" in message_ids

        # Check file counts
        for msg in data["message_ids"]:
            if msg["message_id"] == "SM1":
                assert msg["file_count"] == 2  # audio + full_text
                assert msg["tag"] == "task1"
            elif msg["message_id"] == "SM2":
                assert msg["file_count"] == 1  # audio only
                assert msg["tag"] == "task2"

    def test_list_files_full_format_explicit(self, client, setup_s3_bucket):
        """Test listing files with output_format=full."""
        response = client.get(
            "/files/list",
            params={
                "company_id": "company123",
                "message_intent": "job-to-be-done",
                "output_format": "full",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) == 3


class TestIntegrationByMessage:
    """Integration tests for the /files/by-message endpoint."""

    def test_get_files_by_message_success(self, client, setup_s3_bucket):
        """Test successful retrieval of all artifacts for a message."""
        response = client.get(
            "/files/by-message",
            params={"company_id": "company123", "message_id": "SM1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message_id"] == "SM1"
        assert data["company_id"] == "company123"
        assert data["intent"] == "job-to-be-done"
        assert data["tag"] == "task1"
        assert len(data["files"]) == 2  # audio + full_text

        # Check file types
        file_types = [f["type"] for f in data["files"]]
        assert "audio" in file_types
        assert "full_text" in file_types

        # Verify keys are correct
        keys = [f["key"] for f in data["files"]]
        assert any("SM1_audio.ogg" in k for k in keys)
        assert any("SM1_full_text.txt" in k for k in keys)

    def test_get_files_by_message_different_intent(self, client, setup_s3_bucket):
        """Test retrieval from knowledge-document intent."""
        response = client.get(
            "/files/by-message",
            params={"company_id": "company123", "message_id": "SM3"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message_id"] == "SM3"
        assert data["intent"] == "knowledge-document"
        assert data["tag"] == "doc1"
        assert len(data["files"]) == 1
        assert data["files"][0]["type"] == "full_text"

    def test_get_files_by_message_not_found(self, client, setup_s3_bucket):
        """Test that requesting a non-existent message returns 404."""
        response = client.get(
            "/files/by-message",
            params={"company_id": "company123", "message_id": "SM999999"},
        )

        assert response.status_code == 404
        assert "No artifacts found" in response.json()["detail"]

    def test_get_files_by_message_different_company(self, client, setup_s3_bucket):
        """Test that message from different company returns 404."""
        # SM4 belongs to another_company, not company123
        response = client.get(
            "/files/by-message",
            params={"company_id": "company123", "message_id": "SM4"},
        )

        assert response.status_code == 404
        assert "No artifacts found" in response.json()["detail"]

    def test_get_files_by_message_correct_company(self, client, setup_s3_bucket):
        """Test that message is found when using correct company."""
        response = client.get(
            "/files/by-message",
            params={"company_id": "another_company", "message_id": "SM4"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message_id"] == "SM4"
        assert data["company_id"] == "another_company"
