"""Tests for API middleware."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class TestAPIKeyMiddleware:
    """Tests for API key validation middleware."""

    def test_health_check_bypasses_auth(self):
        """Test that health check works without API key."""
        # Import here to ensure fresh app instance with API key
        from data_api_server.main import app

        with patch("data_api_server.main.settings") as mock_settings:
            mock_settings.api_key = "secret-key-123"
            client = TestClient(app)

            # Health check should work without API key
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "healthy"}

    def test_endpoints_require_api_key_when_configured(self):
        """Test that endpoints require API key when it's configured."""
        from data_api_server.main import app

        with patch("data_api_server.main.settings") as mock_settings:
            mock_settings.api_key = "secret-key-123"
            client = TestClient(app)

            # Request without API key should return 403
            response = client.get(
                "/files/list",
                params={"company_id": "test", "message_intent": "job-to-be-done"},
            )
            assert response.status_code == 403
            assert response.json()["message"] == "Forbidden"

    def test_endpoints_accept_valid_api_key(self):
        """Test that endpoints accept valid API key."""
        from data_api_server.main import app

        with patch("data_api_server.main.settings") as mock_settings:
            with patch("data_api_server.main.s3_service") as mock_s3:
                from ai_voice_shared.models import S3ListResponse

                mock_settings.api_key = "secret-key-123"
                mock_s3.list_objects = AsyncMock(
                    return_value=S3ListResponse(files=[], nextContinuationToken=None)
                )

                client = TestClient(app)

                # Request with valid API key should succeed
                response = client.get(
                    "/files/list",
                    params={"company_id": "test", "message_intent": "job-to-be-done"},
                    headers={"x-api-key": "secret-key-123"},
                )
                assert response.status_code == 200

    def test_endpoints_reject_invalid_api_key(self):
        """Test that endpoints reject invalid API key."""
        from data_api_server.main import app

        with patch("data_api_server.main.settings") as mock_settings:
            mock_settings.api_key = "secret-key-123"
            client = TestClient(app)

            # Request with wrong API key should return 403
            response = client.get(
                "/files/list",
                params={"company_id": "test", "message_intent": "job-to-be-done"},
                headers={"x-api-key": "wrong-key"},
            )
            assert response.status_code == 403
            assert response.json()["message"] == "Forbidden"

    def test_no_auth_when_api_key_not_configured(self):
        """Test that authentication is skipped when API key is None."""
        from data_api_server.main import app

        with patch("data_api_server.main.settings") as mock_settings:
            with patch("data_api_server.main.s3_service") as mock_s3:
                from ai_voice_shared.models import S3ListResponse

                # API key is None (not configured)
                mock_settings.api_key = None
                mock_s3.list_objects = AsyncMock(
                    return_value=S3ListResponse(files=[], nextContinuationToken=None)
                )

                client = TestClient(app)

                # Request without API key should succeed when auth is disabled
                response = client.get(
                    "/files/list",
                    params={"company_id": "test", "message_intent": "job-to-be-done"},
                )
                assert response.status_code == 200

    def test_case_sensitive_header_name(self):
        """Test that x-api-key header is case-sensitive (lowercase)."""
        from data_api_server.main import app

        with patch("data_api_server.main.settings") as mock_settings:
            with patch("data_api_server.main.s3_service") as mock_s3:
                from ai_voice_shared.models import S3ListResponse

                mock_settings.api_key = "secret-key-123"
                mock_s3.list_objects = AsyncMock(
                    return_value=S3ListResponse(files=[], nextContinuationToken=None)
                )
                client = TestClient(app)

                # FastAPI/Starlette normalizes headers to lowercase, so this should work
                response = client.get(
                    "/files/list",
                    params={"company_id": "test", "message_intent": "job-to-be-done"},
                    headers={"X-API-KEY": "secret-key-123"},  # Uppercase
                )
                # Should work due to header normalization
                assert response.status_code == 200

    def test_multiple_endpoints_protected(self):
        """Test that all endpoints (except health) are protected."""
        from data_api_server.main import app

        with patch("data_api_server.main.settings") as mock_settings:
            mock_settings.api_key = "secret-key-123"
            client = TestClient(app)

            # Test /files/list
            response = client.get(
                "/files/list",
                params={"company_id": "test", "message_intent": "job-to-be-done"},
            )
            assert response.status_code == 403

            # Test /files/get-download-url
            response = client.get(
                "/files/get-download-url",
                params={"key": "test.ogg"},
            )
            assert response.status_code == 403
