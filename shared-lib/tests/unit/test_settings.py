import pytest
from pydantic import ValidationError
from ai_voice_shared.settings import CustomerLookupSettings, S3Settings

def test_customer_lookup_settings_valid(monkeypatch):
    monkeypatch.setenv("CUSTOMER_LOOKUP_LAMBDA_FUNCTION_NAME", "test-lookup-function")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    settings = CustomerLookupSettings()
    assert settings.customer_lookup_lambda_function_name == "test-lookup-function"
    assert settings.aws_region == "us-east-1"

def test_customer_lookup_settings_missing_variable(monkeypatch):
    monkeypatch.delenv("CUSTOMER_LOOKUP_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    with pytest.raises(ValidationError):
        CustomerLookupSettings()

def test_s3_settings_valid(monkeypatch):
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
