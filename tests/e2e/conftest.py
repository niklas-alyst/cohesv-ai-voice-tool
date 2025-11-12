"""Pytest configuration and shared fixtures for E2E tests."""

import os
import sys
import pytest
import boto3
from dotenv import load_dotenv
from typing import Dict, Any
import httpx

# Add e2e directory to Python path so we can import utils module
sys.path.insert(0, os.path.dirname(__file__))


@pytest.fixture(scope="session", autouse=True)
def load_e2e_env():
    """Load E2E test environment variables from .env.e2e"""
    # Look for .env.e2e in both e2e/ directory and tests/ directory (parent)
    env_file_local = os.path.join(os.path.dirname(__file__), ".env.e2e")
    env_file_parent = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env.e2e")

    env_file = env_file_parent if os.path.exists(env_file_parent) else env_file_local

    if not os.path.exists(env_file):
        pytest.fail(
            f"E2E configuration file not found at {env_file_parent} or {env_file_local}\n"
            "Please run 'make setup-system-e2e' from the project root."
        )
    load_dotenv(env_file)


@pytest.fixture(scope="session")
def e2e_config() -> Dict[str, Any]:
    """Load and validate E2E test configuration."""
    required_vars = [
        "E2E_WEBHOOK_URL",
        "E2E_DATA_API_URL",
        "E2E_DATA_API_KEY",
        "E2E_S3_BUCKET",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_ACCOUNT_SID",
        "E2E_TEST_COMPANY_ID",
        "E2E_TEST_CUSTOMER_ID",
        "E2E_TEST_PHONE_NUMBER",
    ]

    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        pytest.fail(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Please configure .env.e2e file."
        )

    return {
        "webhook_url": os.getenv("E2E_WEBHOOK_URL"),
        "data_api_url": os.getenv("E2E_DATA_API_URL"),
        "data_api_key": os.getenv("E2E_DATA_API_KEY"),
        "s3_bucket": os.getenv("E2E_S3_BUCKET"),
        "aws_region": os.getenv("AWS_REGION", "ap-southeast-2"),
        "aws_profile": os.getenv("AWS_PROFILE"),
        "twilio_auth_token": os.getenv("TWILIO_AUTH_TOKEN"),
        "twilio_account_sid": os.getenv("TWILIO_ACCOUNT_SID"),
        "twilio_whatsapp_number": os.getenv("TWILIO_WHATSAPP_NUMBER"),
        "test_company_id": os.getenv("E2E_TEST_COMPANY_ID"),
        "test_customer_id": os.getenv("E2E_TEST_CUSTOMER_ID"),
        "test_phone_number": os.getenv("E2E_TEST_PHONE_NUMBER"),
        "timeout_seconds": int(os.getenv("E2E_TEST_TIMEOUT_SECONDS", "90")),
        "cleanup_on_failure": os.getenv("E2E_CLEANUP_ON_FAILURE", "true").lower() == "true",
    }


@pytest.fixture(scope="session")
def s3_client(e2e_config: Dict[str, Any]):
    """AWS S3 client for E2E tests."""
    session_kwargs = {"region_name": e2e_config["aws_region"]}
    if e2e_config["aws_profile"]:
        session_kwargs["profile_name"] = e2e_config["aws_profile"]

    session = boto3.Session(**session_kwargs)
    return session.client("s3")


@pytest.fixture(scope="session")
async def http_client():
    """Async HTTP client for API requests."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest.fixture
def test_message_id(request) -> str:
    """Generate unique message ID for each test."""
    import uuid
    # Include test name for easier debugging
    test_name = request.node.name.replace("test_", "")[:20]
    return f"E2E_{test_name}_{uuid.uuid4().hex[:8]}"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test (requires AWS infrastructure)"
    )
