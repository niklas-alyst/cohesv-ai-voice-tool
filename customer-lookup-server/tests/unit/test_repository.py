import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
import json

from customer_lookup_server.core.repository import CustomerRepository


@pytest.fixture
def mock_boto3_client_function():
    """Fixture to mock the boto3.client function."""
    with patch("boto3.client") as mock_boto_client:
        yield mock_boto_client


@pytest.fixture
def mock_s3_client_instance(mock_boto3_client_function):
    """Fixture to provide the mocked S3 client instance."""
    mock_s3 = MagicMock()
    mock_boto3_client_function.return_value = mock_s3
    return mock_s3


@pytest.fixture
def sample_customers_data():
    """Fixture for sample customer data."""
    return [
        {
            "customer_id": "cust_123",
            "company_id": "comp_abc",
            "company_name": "Acme Corp",
            "phone_number": "+14155552671",
        },
        {
            "customer_id": "cust_456",
            "company_id": "comp_xyz",
            "company_name": "Stark Industries",
            "phone_number": "+15105552671",
        },
    ]


class TestCustomerRepository:
    """Unit tests for CustomerRepository."""

    def test_init(self, mock_boto3_client_function, mock_s3_client_instance):
        """Test initialization of the repository."""
        repo = CustomerRepository(s3_bucket="test-bucket", s3_key="test-key.json")
        assert repo.s3_bucket == "test-bucket"
        assert repo.s3_key == "test-key.json"
        mock_boto3_client_function.assert_called_once_with("s3")
        assert repo.s3_client == mock_s3_client_instance
        assert repo._customers is None

    def test_load_customers_success(self, mock_s3_client_instance, sample_customers_data):
        """Test successful loading of customers from S3."""
        mock_s3_client_instance.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(sample_customers_data).encode("utf-8"))
        }

        repo = CustomerRepository()
        customers = repo._load_customers()

        mock_s3_client_instance.get_object.assert_called_once_with(
            Bucket="cohesv-ai-voice-tool", Key="customers.json"
        )
        assert customers == sample_customers_data
        assert repo._customers == sample_customers_data

    def test_load_customers_caching(self, mock_s3_client_instance, sample_customers_data):
        """Test that customers data is cached after first load."""
        mock_s3_client_instance.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(sample_customers_data).encode("utf-8"))
        }

        repo = CustomerRepository()
        repo._load_customers()
        repo._load_customers()  # Call again to test caching

        mock_s3_client_instance.get_object.assert_called_once()  # Should only be called once

    def test_load_customers_s3_error(self, mock_s3_client_instance):
        """Test error handling when S3 access fails."""
        mock_s3_client_instance.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "GetObject"
        )

        repo = CustomerRepository()
        with pytest.raises(ClientError):
            repo._load_customers()

    def test_find_by_phone_number_found(self, mock_s3_client_instance, sample_customers_data):
        """Test finding a customer by phone number."""
        mock_s3_client_instance.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(sample_customers_data).encode("utf-8"))
        }

        repo = CustomerRepository()
        found_customer = repo.find_by_phone_number(phone_number="+14155552671")

        expected_customer = {
            "customer_id": "cust_123",
            "company_id": "comp_abc",
            "company_name": "Acme Corp",
        }
        assert found_customer == expected_customer

    def test_find_by_phone_number_not_found(self, mock_s3_client_instance, sample_customers_data):
        """Test not finding a customer by phone number."""
        mock_s3_client_instance.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(sample_customers_data).encode("utf-8"))
        }

        repo = CustomerRepository()
        found_customer = repo.find_by_phone_number(phone_number="+19999999999")

        assert found_customer is None

    def test_find_by_phone_number_empty_list(self, mock_s3_client_instance):
        """Test finding a customer when the customer list is empty."""
        mock_s3_client_instance.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps([]).encode("utf-8"))
        }

        repo = CustomerRepository()
        found_customer = repo.find_by_phone_number(phone_number="+14155552671")

        assert found_customer is None
