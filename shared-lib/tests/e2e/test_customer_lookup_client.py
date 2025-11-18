"""End-to-end tests for CustomerLookupClient against real deployed API."""

import pytest
import os
from dotenv import load_dotenv
from ai_voice_shared.services.customer_lookup_client import CustomerLookupClient
from ai_voice_shared.settings import CustomerLookupSettings
from ai_voice_shared.models import CustomerMetadata


@pytest.fixture(scope="session", autouse=True)
def load_test_env():
    """Load test environment variables from .env.test"""
    load_dotenv(".env.test")


@pytest.fixture
def customer_lookup_settings():
    """Create CustomerLookupSettings for testing."""
    # Get required values from environment
    wunse_api_base_url = os.getenv("WUNSE_API_BASE_URL")
    wunse_api_key = os.getenv("WUNSE_API_KEY")

    # Validate required settings are present
    if not wunse_api_base_url:
        pytest.skip("WUNSE_API_BASE_URL not set in environment")
    if not wunse_api_key or wunse_api_key == "your-wunse-api-key-here":
        pytest.skip("WUNSE_API_KEY not set in environment or still has placeholder value")

    return CustomerLookupSettings(
        wunse_api_base_url=wunse_api_base_url,
        wunse_api_key=wunse_api_key
    )


@pytest.fixture
def test_phone_number():
    """Get test phone number from environment or skip test."""
    phone = os.getenv("TEST_CUSTOMER_PHONE_NUMBER")
    if not phone or phone == "your-test-phone-number":
        pytest.skip("TEST_CUSTOMER_PHONE_NUMBER not set in .env.test - add a valid test customer phone number")
    return phone


@pytest.fixture
def customer_lookup_client(customer_lookup_settings):
    """Create CustomerLookupClient for testing."""
    return CustomerLookupClient(settings=customer_lookup_settings)


@pytest.mark.e2e
class TestCustomerLookupClient:
    """End-to-end tests for CustomerLookupClient against real deployed API."""

    @pytest.mark.asyncio
    async def test_fetch_customer_metadata_with_valid_phone_number(
        self, customer_lookup_client, test_phone_number
    ):
        """Test fetching customer metadata with a valid phone number."""
        # Fetch customer metadata
        customer_metadata = await customer_lookup_client.fetch_customer_metadata(test_phone_number)

        # Assertions
        assert isinstance(customer_metadata, CustomerMetadata)
        assert customer_metadata.customer_id  # Has a customer_id
        assert customer_metadata.company_id   # Has a company_id
        assert customer_metadata.company_name # Has a company_name

    @pytest.mark.asyncio
    async def test_fetch_customer_metadata_with_whatsapp_prefix(
        self, customer_lookup_client, test_phone_number
    ):
        """Test fetching customer metadata with whatsapp: prefix."""
        # Add whatsapp: prefix to test phone number
        phone_number = f"whatsapp:{test_phone_number}"

        # Fetch customer metadata
        customer_metadata = await customer_lookup_client.fetch_customer_metadata(phone_number)

        # Assertions
        assert isinstance(customer_metadata, CustomerMetadata)
        assert customer_metadata.customer_id  # Has a customer_id
        assert customer_metadata.company_id   # Has a company_id
        assert customer_metadata.company_name # Has a company_name

    @pytest.mark.asyncio
    async def test_fetch_customer_metadata_with_nonexistent_phone_number(
        self, customer_lookup_client
    ):
        """Test fetching customer metadata with a phone number not in the system."""
        # Using a phone number that doesn't exist
        phone_number = "+14155552671"

        # Should raise ValueError for non-existent customer
        with pytest.raises(ValueError) as exc_info:
            await customer_lookup_client.fetch_customer_metadata(phone_number)

        assert "Customer not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_customer_metadata_validates_response(
        self, customer_lookup_client, test_phone_number
    ):
        """Test that response is properly validated as CustomerMetadata model."""
        # Fetch customer metadata
        customer_metadata = await customer_lookup_client.fetch_customer_metadata(test_phone_number)

        # Verify it's a proper Pydantic model with all required fields
        assert hasattr(customer_metadata, "customer_id")
        assert hasattr(customer_metadata, "company_id")
        assert hasattr(customer_metadata, "company_name")

        # Verify fields are strings
        assert isinstance(customer_metadata.customer_id, str)
        assert isinstance(customer_metadata.company_id, str)
        assert isinstance(customer_metadata.company_name, str)
