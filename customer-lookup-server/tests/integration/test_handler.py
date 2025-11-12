import pytest
import json
from unittest.mock import patch

from customer_lookup_server.handler import lambda_handler
from customer_lookup_server.core.repository import CustomerRepository


@pytest.fixture
def mock_customer_repository():
    """Fixture to mock the CustomerRepository instance."""
    with patch("customer_lookup_server.handler.repository", spec=CustomerRepository) as mock_repo:
        yield mock_repo


@pytest.fixture
def sample_customer_data():
    """Fixture for sample customer data."""
    return {
        "customer_id": "cust_123",
        "company_id": "comp_abc",
        "company_name": "Acme Corp",
    }


class TestLambdaHandler:
    """Integration tests for the lambda_handler function."""

    def test_customer_found_200_ok(self, mock_customer_repository, sample_customer_data):
        """Test case where a customer is found."""
        mock_customer_repository.find_by_phone_number.return_value = sample_customer_data

        event = {"phone_number": "+14155552671"}
        response = lambda_handler(event, {})

        assert response["statusCode"] == 200
        assert json.loads(response["body"]) == sample_customer_data
        mock_customer_repository.find_by_phone_number.assert_called_once_with("+14155552671")

    def test_customer_not_found_404(self, mock_customer_repository):
        """Test case where no customer is found."""
        mock_customer_repository.find_by_phone_number.return_value = None

        event = {"phone_number": "+19999999999"}
        response = lambda_handler(event, {})

        assert response["statusCode"] == 404
        assert "Customer not found" in json.loads(response["body"])["error"]
        mock_customer_repository.find_by_phone_number.assert_called_once_with("+19999999999")

    def test_missing_phone_number_400(self, mock_customer_repository):
        """Test case for missing phone_number in the event."""
        event = {}  # Missing phone_number
        response = lambda_handler(event, {})

        assert response["statusCode"] == 400
        assert "Missing phone_number parameter" in json.loads(response["body"])["error"]
        mock_customer_repository.find_by_phone_number.assert_not_called()

    def test_phone_number_cleaning(self, mock_customer_repository, sample_customer_data):
        """Test that the 'whatsapp:' prefix is removed from the phone number."""
        mock_customer_repository.find_by_phone_number.return_value = sample_customer_data

        event = {"phone_number": "whatsapp:+14155552671"}
        response = lambda_handler(event, {})

        assert response["statusCode"] == 200
        mock_customer_repository.find_by_phone_number.assert_called_once_with("+14155552671")

    def test_internal_server_error_500(self, mock_customer_repository):
        """Test case for an unexpected internal error."""
        mock_customer_repository.find_by_phone_number.side_effect = Exception("Test error")

        event = {"phone_number": "+14155552671"}
        response = lambda_handler(event, {})

        assert response["statusCode"] == 500
        assert "Internal server error" in json.loads(response["body"])["error"]
        mock_customer_repository.find_by_phone_number.assert_called_once_with("+14155552671")
