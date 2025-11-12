# Shared Library (`shared-lib`)

This directory contains a Python package (`ai_voice_shared`) that serves as a central repository for common code, data models, and client implementations shared across the various microservices in the AI Voice Tool monorepo.

## Overview

The primary goal of the shared library is to promote code reusability, maintain consistency in data structures, and reduce boilerplate code across different services. It encapsulates functionalities and definitions that are fundamental to the interoperation and overall architecture of the system.

## Contents

The `ai_voice_shared` package is structured into the following key components:

### 1. `models.py`

Contains Pydantic models for data validation and serialization. These models define the expected structure of data payloads exchanged between services or with external APIs.

**Key Models:**
-   `TwilioWebhookPayload`: Defines the structure of incoming Twilio WhatsApp webhook events.
-   `CustomerMetadata`: Represents the metadata retrieved for a customer (e.g., `customer_id`, `company_id`, `company_name`).
-   `S3ListResponse`, `S3ObjectMetadata`: Models for listing S3 objects.

### 2. `settings.py`

Houses Pydantic `BaseSettings` classes for managing shared configuration parameters. This ensures a consistent approach to environment variable loading and validation across services that utilize these common settings.

**Key Settings:**
-   `S3Settings`: Configuration related to AWS S3 bucket names and regions.

### 3. `services/`

Provides client implementations for interacting with common external services or other internal microservices. This abstracts away the underlying communication logic, allowing services to interact through well-defined interfaces.

**Key Services/Clients:**
-   `s3_service.py`: `S3Service` class for performing common S3 operations (e.g., upload, download, list objects, generate presigned URLs).
-   `customer_lookup_client.py`: `CustomerLookupClient` for making requests to the `customer-lookup-server` to retrieve customer metadata.

## Benefits

-   **Consistency**: Ensures all services use the same data models and interfaces.
-   **Reusability**: Avoids duplicating code for common tasks like S3 interactions or external API calls.
-   **Maintainability**: Changes to shared logic or data structures can be managed in a single place.
-   **Reduced Boilerplate**: Simplifies service development by providing ready-to-use clients and utilities.

## Usage Example

To use a component from the shared library, simply import it into your service's code:

```python
# Example: In webhook-handler/webhook_handler/handler.py
from ai_voice_shared import CustomerLookupClient, TwilioWebhookPayload

# Example: In voice-parser/voice_parser/core/processor.py
from ai_voice_shared.services.s3_service import S3Service
```

## Testing

The shared library has its own test suite to ensure reliability of common code used across all services.

### Test Structure

```
tests/
├── unit/              # Unit tests (mocked dependencies)
└── integration/       # Integration tests (test against real AWS services)
    └── external_services/
        ├── test_customer_lookup_client.py
        └── test_s3_service.py
```

- **Unit tests**: Test individual functions/classes with all external dependencies mocked
- **Integration tests**: Test clients against real AWS services (S3, Lambda)

### Running Tests

```bash
# Run all tests
cd shared-lib
uv run pytest tests -v

# Run unit tests only
uv run pytest tests/unit -v

# Run integration tests only (requires AWS credentials)
uv run pytest tests/integration -v

# Using markers
uv run pytest -m unit              # Unit tests
uv run pytest -m integration       # Integration tests
uv run pytest -m "not integration" # Skip integration tests
```

### Integration Test Requirements

Integration tests require:
1. AWS credentials configured (via `AWS_PROFILE` or credentials file)
2. `.env.test` file with test configuration:
   ```bash
   AWS_REGION=ap-southeast-2
   AWS_PROFILE=cohesv
   S3_BUCKET_NAME=your-test-bucket
   ```
3. Deployed AWS resources (S3 bucket, customer-lookup Lambda)

**Note**: Integration tests interact with real AWS services and may incur costs.

## Development

### Adding New Shared Code

When adding new shared functionality:

1. Add the code to the appropriate module (`models.py`, `settings.py`, or `services/`)
2. Write unit tests in `tests/unit/`
3. If the code interacts with external services, add integration tests in `tests/integration/`
4. Run linting: `uv run ruff check`
5. Run tests: `uv run pytest tests -v`

### Modifying Existing Code

When modifying shared library code:

1. Update the relevant tests
2. Run the full test suite to ensure no services are broken
3. Test in dependent services before committing
