"""End-to-end tests for CustomerLookupClient against real deployed Lambda."""

import pytest
from ai_voice_shared.services.customer_lookup_client import CustomerLookupClient
from ai_voice_shared.settings import CustomerLookupSettings
from ai_voice_shared.models import CustomerMetadata


@pytest.fixture
def customer_lookup_settings():
    """Create CustomerLookupSettings for testing."""
    return CustomerLookupSettings(
        customer_lookup_lambda_function_name="ai-voice-tool-customer-lookup-server",
        aws_region="ap-southeast-2"
    )


@pytest.fixture
def customer_lookup_client(customer_lookup_settings):
    """Create CustomerLookupClient for testing."""
    return CustomerLookupClient(settings=customer_lookup_settings)


@pytest.mark.e2e
class TestCustomerLookupClient:
    """End-to-end tests for CustomerLookupClient against real deployed Lambda."""

    @pytest.mark.asyncio
    async def test_fetch_customer_metadata_with_valid_phone_number(
        self, customer_lookup_client
    ):
        """Test fetching customer metadata with a valid phone number."""
        # Using hardcoded phone number from repository
        phone_number = "+61400000000"

        # Fetch customer metadata
        customer_metadata = await customer_lookup_client.fetch_customer_metadata(phone_number)

        # Assertions
        assert isinstance(customer_metadata, CustomerMetadata)
        assert customer_metadata.customer_id == "cust_dummy_001"
        assert customer_metadata.company_id == "comp_dummy_001"
        assert customer_metadata.company_name == "Dummy Test Company"

    @pytest.mark.asyncio
    async def test_fetch_customer_metadata_with_whatsapp_prefix(
        self, customer_lookup_client
    ):
        """Test fetching customer metadata with whatsapp: prefix."""
        # Using hardcoded phone number with whatsapp prefix
        phone_number = "whatsapp:+61400000000"

        # Fetch customer metadata
        customer_metadata = await customer_lookup_client.fetch_customer_metadata(phone_number)

        # Assertions
        assert isinstance(customer_metadata, CustomerMetadata)
        assert customer_metadata.customer_id == "cust_dummy_001"
        assert customer_metadata.company_id == "comp_dummy_001"
        assert customer_metadata.company_name == "Dummy Test Company"

    @pytest.mark.asyncio
    async def test_fetch_customer_metadata_with_nonexistent_phone_number(
        self, customer_lookup_client
    ):
        """Test fetching customer metadata with a phone number not in the repository."""
        # Using a phone number that doesn't exist in the hardcoded data
        phone_number = "+14155552671"

        # Should raise ValueError for non-existent customer
        with pytest.raises(ValueError) as exc_info:
            await customer_lookup_client.fetch_customer_metadata(phone_number)

        assert "Customer not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_customer_metadata_validates_response(
        self, customer_lookup_client
    ):
        """Test that response is properly validated as CustomerMetadata model."""
        # Using hardcoded phone number from repository
        phone_number = "+61400000000"

        # Fetch customer metadata
        customer_metadata = await customer_lookup_client.fetch_customer_metadata(phone_number)

        # Verify it's a proper Pydantic model with all required fields
        assert hasattr(customer_metadata, "customer_id")
        assert hasattr(customer_metadata, "company_id")
        assert hasattr(customer_metadata, "company_name")

        # Verify fields are strings
        assert isinstance(customer_metadata.customer_id, str)
        assert isinstance(customer_metadata.company_id, str)
        assert isinstance(customer_metadata.company_name, str)
