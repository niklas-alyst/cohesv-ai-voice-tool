import pytest
from pydantic import ValidationError
from ai_voice_shared.settings import CustomerLookupSettings, S3Settings

def test_customer_lookup_settings_valid(monkeypatch):
    monkeypatch.setenv("WUNSE_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("WUNSE_API_KEY", "test-api-key-123")
    settings = CustomerLookupSettings()
    assert settings.wunse_api_base_url == "https://api.example.com"
    assert settings.wunse_api_key == "test-api-key-123"

def test_customer_lookup_settings_missing_variable(monkeypatch):
    monkeypatch.delenv("WUNSE_API_BASE_URL", raising=False)
    monkeypatch.setenv("WUNSE_API_KEY", "test-api-key")
    with pytest.raises(ValidationError):
        CustomerLookupSettings()

def test_s3_settings_valid(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("S3_BUCKET_NAME", "test-s3-bucket")
    settings = S3Settings()
    assert settings.aws_region == "us-west-2"
    assert settings.s3_bucket_name == "test-s3-bucket"
    assert settings.aws_profile is None # Default value

def test_s3_settings_valid_with_profile(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "eu-central-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "another-s3-bucket")
    monkeypatch.setenv("AWS_PROFILE", "test-profile")
    settings = S3Settings()
    assert settings.aws_region == "eu-central-1"
    assert settings.s3_bucket_name == "another-s3-bucket"
    assert settings.aws_profile == "test-profile"

def test_s3_settings_missing_required_variable(monkeypatch):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    with pytest.raises(ValidationError):
        S3Settings()
