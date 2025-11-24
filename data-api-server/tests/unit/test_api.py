"""Tests for API endpoints."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from ai_voice_shared.models import (
    S3ListResponse,
    S3ObjectMetadata,
    S3ListIdsResponse,
    MessageIdSummary,
    MessageArtifactsResponse,
    MessageArtifact,
)
# Removed: from data_api_server.main import app


@pytest.fixture
def client():
    """Create test client."""
    # Set environment variables before importing app
    os.environ["S3_BUCKET_NAME"] = "test-bucket"
    os.environ["API_KEY"] = "" # Disable API key for unit tests

    from data_api_server.main import app
    return TestClient(app)


@pytest.fixture
def mock_s3_service():
    """Mock S3Service to avoid external dependencies."""
    with patch("data_api_server.main.s3_service") as mock:
        yield mock


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health check returns 200 and correct status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestListFilesEndpoint:
    """Tests for /files/list endpoint."""

    def test_list_files_success(self, client, mock_s3_service):
        """Test successful listing of files."""
        # Mock response
        mock_s3_service.list_objects = AsyncMock(
            return_value=S3ListResponse(
                files=[
                    S3ObjectMetadata(
                        key="company123/job-to-be-done/test_SM123_audio.ogg",
                        etag='"abc123"',
                        size=12345,
                        last_modified="2025-11-05T14:30:01Z",
                    ),
                    S3ObjectMetadata(
                        key="company123/job-to-be-done/test_SM123_full_text.txt",
                        etag='"def456"',
                        size=1024,
                        last_modified="2025-11-05T14:30:02Z",
                    ),
                ],
                nextContinuationToken=None,
            )
        )

        response = client.get(
            "/files/list",
            params={"company_id": "company123", "message_intent": "job-to-be-done"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) == 2
        assert data["files"][0]["key"] == "company123/job-to-be-done/test_SM123_audio.ogg"
        assert data["nextContinuationToken"] is None

        # Verify S3Service was called correctly
        mock_s3_service.list_objects.assert_called_once_with(
            company_id="company123",
            message_intent="job-to-be-done",
            continuation_token=None,
        )

    def test_list_files_with_pagination(self, client, mock_s3_service):
        """Test listing with continuation token."""
        mock_s3_service.list_objects = AsyncMock(
            return_value=S3ListResponse(
                files=[],
                nextContinuationToken="next_token_123",
            )
        )

        response = client.get(
            "/files/list",
            params={
                "company_id": "company123",
                "message_intent": "knowledge-document",
                "nextContinuationToken": "token_abc",
            },
        )

        assert response.status_code == 200
        assert response.json()["nextContinuationToken"] == "next_token_123"

        mock_s3_service.list_objects.assert_called_once_with(
            company_id="company123",
            message_intent="knowledge-document",
            continuation_token="token_abc",
        )

    def test_list_files_invalid_intent(self, client):
        """Test that invalid message_intent returns 400."""
        response = client.get(
            "/files/list",
            params={"company_id": "company123", "message_intent": "invalid-intent"},
        )

        assert response.status_code == 400
        assert "Invalid message_intent" in response.json()["detail"]

    def test_list_files_missing_required_params(self, client):
        """Test that missing required params returns 422."""
        # Missing both params
        response = client.get("/files/list")
        assert response.status_code == 422

        # Missing message_intent
        response = client.get("/files/list", params={"company_id": "company123"})
        assert response.status_code == 422

        # Missing company_id
        response = client.get(
            "/files/list", params={"message_intent": "job-to-be-done"}
        )
        assert response.status_code == 422

    def test_list_files_s3_error(self, client, mock_s3_service):
        """Test that S3 errors return 500."""
        mock_s3_service.list_objects = AsyncMock(
            side_effect=Exception("S3 connection failed")
        )

        response = client.get(
            "/files/list",
            params={"company_id": "company123", "message_intent": "job-to-be-done"},
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    def test_list_files_all_valid_intents(self, client, mock_s3_service):
        """Test all three valid message intents."""
        mock_s3_service.list_objects = AsyncMock(
            return_value=S3ListResponse(files=[], nextContinuationToken=None)
        )

        valid_intents = ["job-to-be-done", "knowledge-document", "other"]

        for intent in valid_intents:
            response = client.get(
                "/files/list",
                params={"company_id": "test_company", "message_intent": intent},
            )
            assert response.status_code == 200


class TestGetDownloadUrlEndpoint:
    """Tests for /files/get-download-url endpoint."""

    def test_get_download_url_success(self, client, mock_s3_service):
        """Test successful presigned URL generation."""
        mock_s3_service.generate_presigned_url = AsyncMock(
            return_value="https://s3.amazonaws.com/bucket/key?presigned=params"
        )

        response = client.get(
            "/files/get-download-url",
            params={"key": "company123%2Fjob-to-be-done%2Ftest_SM123_audio.ogg"},
        )

        assert response.status_code == 200
        assert response.json()["url"] == "https://s3.amazonaws.com/bucket/key?presigned=params"

        # Verify URL-decoding happened
        mock_s3_service.generate_presigned_url.assert_called_once_with(
            "company123/job-to-be-done/test_SM123_audio.ogg"
        )

    def test_get_download_url_file_not_found(self, client, mock_s3_service):
        """Test that non-existent file returns 404."""
        mock_s3_service.generate_presigned_url = AsyncMock(
            side_effect=ValueError("Object not found")
        )

        response = client.get(
            "/files/get-download-url",
            params={"key": "company123%2Fnonexistent.ogg"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "File not found"

    def test_get_download_url_s3_error(self, client, mock_s3_service):
        """Test that S3 errors return 500."""
        mock_s3_service.generate_presigned_url = AsyncMock(
            side_effect=Exception("S3 connection failed")
        )

        response = client.get(
            "/files/get-download-url",
            params={"key": "company123%2Ftest.ogg"},
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    def test_get_download_url_missing_key(self, client):
        """Test that missing key param returns 422."""
        response = client.get("/files/get-download-url")
        assert response.status_code == 422

    def test_get_download_url_special_chars(self, client, mock_s3_service):
        """Test URL decoding with special characters."""
        mock_s3_service.generate_presigned_url = AsyncMock(
            return_value="https://s3.amazonaws.com/bucket/key"
        )

        # Test with spaces and special chars
        encoded_key = "company%20123/job-to-be-done/test%20file%20%26%20stuff.ogg"
        response = client.get(
            "/files/get-download-url",
            params={"key": encoded_key},
        )

        assert response.status_code == 200

        # Verify the decoded key was passed to S3Service
        expected_key = "company 123/job-to-be-done/test file & stuff.ogg"
        mock_s3_service.generate_presigned_url.assert_called_once_with(expected_key)


class TestListFilesWithOutputFormat:
    """Tests for /files/list endpoint with output_format parameter."""

    def test_list_files_with_ids_format(self, client, mock_s3_service):
        """Test listing with output_format=ids."""
        mock_s3_service.list_objects_ids_only = AsyncMock(
            return_value=S3ListIdsResponse(
                message_ids=[
                    MessageIdSummary(
                        message_id="SM123456",
                        tag="bathroom-renovation",
                        file_count=3,
                    ),
                    MessageIdSummary(
                        message_id="SM789012",
                        tag="leak-repair",
                        file_count=2,
                    ),
                ],
                nextContinuationToken=None,
            )
        )

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
        assert len(data["message_ids"]) == 2
        assert data["message_ids"][0]["message_id"] == "SM123456"
        assert data["message_ids"][0]["tag"] == "bathroom-renovation"
        assert data["message_ids"][0]["file_count"] == 3
        assert data["nextContinuationToken"] is None

        mock_s3_service.list_objects_ids_only.assert_called_once_with(
            company_id="company123",
            message_intent="job-to-be-done",
            continuation_token=None,
        )

    def test_list_files_with_full_format(self, client, mock_s3_service):
        """Test listing with output_format=full (default behavior)."""
        mock_s3_service.list_objects = AsyncMock(
            return_value=S3ListResponse(
                files=[
                    S3ObjectMetadata(
                        key="company123/job-to-be-done/test_SM123_audio.ogg",
                        etag='"abc123"',
                        size=12345,
                        last_modified="2025-11-05T14:30:01Z",
                    )
                ],
                nextContinuationToken=None,
            )
        )

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
        assert len(data["files"]) == 1

        mock_s3_service.list_objects.assert_called_once_with(
            company_id="company123",
            message_intent="job-to-be-done",
            continuation_token=None,
        )

    def test_list_files_default_format(self, client, mock_s3_service):
        """Test that default output_format is 'full'."""
        mock_s3_service.list_objects = AsyncMock(
            return_value=S3ListResponse(files=[], nextContinuationToken=None)
        )

        response = client.get(
            "/files/list",
            params={"company_id": "company123", "message_intent": "job-to-be-done"},
        )

        assert response.status_code == 200
        assert "files" in response.json()

        # Should call list_objects (not list_objects_ids_only)
        mock_s3_service.list_objects.assert_called_once()

    def test_list_files_invalid_format(self, client):
        """Test that invalid output_format returns 400."""
        response = client.get(
            "/files/list",
            params={
                "company_id": "company123",
                "message_intent": "job-to-be-done",
                "output_format": "invalid",
            },
        )

        assert response.status_code == 400
        assert "Invalid output_format" in response.json()["detail"]


class TestByMessageEndpoint:
    """Tests for /files/by-message endpoint."""

    def test_get_files_by_message_success(self, client, mock_s3_service):
        """Test successful retrieval of message artifacts."""
        mock_s3_service.list_files_by_message_id = AsyncMock(
            return_value=MessageArtifactsResponse(
                message_id="SM123456",
                company_id="company123",
                intent="job-to-be-done",
                tag="bathroom-renovation",
                files=[
                    MessageArtifact(
                        key="company123/job-to-be-done/bathroom-renovation_SM123456_audio.ogg",
                        type="audio",
                        etag='"abc123"',
                        size=123456,
                        last_modified="2025-11-05T14:30:01Z",
                    ),
                    MessageArtifact(
                        key="company123/job-to-be-done/bathroom-renovation_SM123456_full_text.txt",
                        type="full_text",
                        etag='"def456"',
                        size=1024,
                        last_modified="2025-11-05T14:30:02Z",
                    ),
                    MessageArtifact(
                        key="company123/job-to-be-done/bathroom-renovation_SM123456.text_summary.txt",
                        type="text_summary",
                        etag='"ghi789"',
                        size=512,
                        last_modified="2025-11-05T14:30:03Z",
                    ),
                ],
            )
        )

        response = client.get(
            "/files/by-message",
            params={"company_id": "company123", "message_id": "SM123456"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message_id"] == "SM123456"
        assert data["company_id"] == "company123"
        assert data["intent"] == "job-to-be-done"
        assert data["tag"] == "bathroom-renovation"
        assert len(data["files"]) == 3
        assert data["files"][0]["type"] == "audio"
        assert data["files"][1]["type"] == "full_text"
        assert data["files"][2]["type"] == "text_summary"

        mock_s3_service.list_files_by_message_id.assert_called_once_with(
            company_id="company123",
            message_id="SM123456",
        )

    def test_get_files_by_message_not_found(self, client, mock_s3_service):
        """Test that non-existent message returns 404."""
        mock_s3_service.list_files_by_message_id = AsyncMock(return_value=None)

        response = client.get(
            "/files/by-message",
            params={"company_id": "company123", "message_id": "SM999999"},
        )

        assert response.status_code == 404
        assert "No artifacts found" in response.json()["detail"]

    def test_get_files_by_message_missing_params(self, client):
        """Test that missing required params returns 422."""
        # Missing both params
        response = client.get("/files/by-message")
        assert response.status_code == 422

        # Missing message_id
        response = client.get("/files/by-message", params={"company_id": "company123"})
        assert response.status_code == 422

        # Missing company_id
        response = client.get("/files/by-message", params={"message_id": "SM123456"})
        assert response.status_code == 422

    def test_get_files_by_message_s3_error(self, client, mock_s3_service):
        """Test that S3 errors return 500."""
        mock_s3_service.list_files_by_message_id = AsyncMock(
            side_effect=Exception("S3 connection failed")
        )

        response = client.get(
            "/files/by-message",
            params={"company_id": "company123", "message_id": "SM123456"},
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"
