# GEMINI.md

This file provides guidance to Gemini when working with code in this repository.

## Development Guidelines
- We use `uv` for this project, so all Python code should be run with `uv run ...`
- You may have to call `uv` directly from the binary: `/home/niklas/.local/bin/uv`
- NEVER modify `pyproject.toml` directly, use the corresponding `uv` commands, e.g. `uv add`
- Run linting after each development: `uv run ruff check`
- All services use async/await for I/O operations
- Use Pydantic for all data models and settings

## Project Overview

This is a WhatsApp AI Assistant built on Python and deployed on AWS Lambda. The system processes voice and text messages from WhatsApp via Twilio, extracting actionable items and knowledge documents for business use.

### System Architecture

The platform consists of **four microservices** deployed as Docker-based Lambda functions:

1. **webhook-handler** - Receives Twilio webhooks, validates signatures, authorizes senders, enqueues to SQS
2. **voice-parser** - SQS-triggered worker that processes messages, transcribes audio, analyzes with LLM, stores in S3
3. **customer-lookup-server** - Internal API providing customer metadata for authorization and data partitioning
4. **data-api-server** - FastAPI REST API for accessing processed data with presigned S3 URLs

Plus supporting components:
- **shared-lib** - Common code, models, and clients shared across all services
- **infrastructure** - CloudFormation templates for all AWS resources (ECR, S3, SQS, API Gateway, Lambda)

## Documentation
All microservices are well-documented through README.md files. **This should be your first point of entry for all development tasks.**

Service-specific documentation:
- [webhook-handler/README.md](webhook-handler/README.md) - Twilio webhook validation and SQS enqueueing
- [voice-parser/README.md](voice-parser/README.md) - Message processing pipeline
- [customer-lookup-server/README.md](customer-lookup-server/README.md) - Customer authorization API
- [data-api-server/README.md](data-api-server/README.md) - REST API for data access
- [shared-lib/README.md](shared-lib/README.md) - Common models and utilities
- [infrastructure/README.md](infrastructure/README.md) - Deployment and CloudFormation stacks

## High-Level Architecture

### Message Processing Flow

```
Twilio (WhatsApp) → API Gateway → webhook-handler
    → customer-lookup-server (authorization)
    → SQS Queue → voice-parser (async worker)
        → customer-lookup-server (metadata)
        → Twilio API (download media)
        → OpenAI Whisper (transcribe audio)
        → OpenAI GPT (analyze intent & structure)
        → S3 (store artifacts)
        → Twilio API (send feedback to user)
```

### Data Access Flow

```
Client App → API Gateway → data-api-server
    → S3 (list files by company/intent)
    → S3 (generate presigned URLs)
```

### Key Components

**webhook-handler**
- Entry point for Twilio webhooks (POST)
- Validates Twilio signature (`X-Twilio-Signature`)
- Checks sender authorization via customer-lookup-server
- Enqueues validated `TwilioWebhookPayload` to SQS
- Returns immediate 200 OK to Twilio

**voice-parser**
- SQS-triggered Lambda worker (batch processing)
- Handles both text and audio messages
- Downloads media from Twilio's content URLs
- Transcribes audio with OpenAI Whisper
- Analyzes content with LLM to determine intent:
  - `JOB_TO_BE_DONE` - actionable tasks
  - `KNOWLEDGE_DOCUMENT` - reference information
  - `OTHER` - general messages
- Structures actionable messages into predefined formats
- Uploads all artifacts to S3 under `{company_id}/{intent}/` prefix
- Sends progress updates to users via Twilio
- Uses partial failure handling (returns `batchItemFailures` to SQS)

**customer-lookup-server**
- Internal Lambda-to-Lambda invocation API
- Loads customer data from S3 (`customers.json`)
- Provides customer metadata: `customer_id`, `company_id`, `company_name`
- Used for authorization (webhook-handler) and data partitioning (voice-parser)

**data-api-server**
- FastAPI application on Lambda (with Mangum adapter)
- API key authentication via API Gateway
- Lists S3 files filtered by `company_id` and `message_intent`
- Generates presigned URLs (5 min expiration) for direct S3 downloads
- Never proxies file content - clients download directly from S3

## Monorepo Structure

```
ai-voice-tool/
├── webhook-handler/           # Twilio webhook receiver
│   └── webhook_handler/
│       ├── handler.py         # Lambda entry point
│       └── settings.py        # Configuration
├── voice-parser/              # Message processing worker
│   └── voice_parser/
│       ├── worker.py          # Lambda entry point
│       ├── core/
│       │   ├── processor.py   # Main processing logic
│       │   └── settings.py    # Configuration
│       └── services/
│           ├── transcription.py  # OpenAI Whisper
│           ├── llm.py            # OpenAI GPT
│           └── twilio.py         # Twilio API client
├── customer-lookup-server/    # Customer metadata API
│   └── customer_lookup/
│       ├── handler.py         # Lambda entry point
│       └── settings.py        # Configuration
├── data-api-server/           # REST API for data access
│   └── data_api_server/
│       ├── main.py            # FastAPI app + Lambda handler
│       └── settings.py        # Configuration
├── shared-lib/                # Common code and models
│   └── ai_voice_shared/
│       ├── models.py          # Pydantic models (TwilioWebhookPayload, etc.)
│       ├── settings.py        # Shared settings (S3Settings)
│       └── services/
│           ├── s3_service.py         # S3 operations
│           └── customer_lookup_client.py  # Customer lookup client
└── infrastructure/            # CloudFormation IaC
    ├── ecr/                   # Container registries
    ├── shared/                # S3, SQS, API Gateway
    ├── customer-lookup-server/
    ├── voice-parser/
    ├── webhook-handler/
    ├── data-api-server/
    └── parameters/            # Environment configs
```

**Key Architectural Decisions:**
- All services deployed as Docker-based Lambda functions
- ECR for container image storage
- SQS for decoupling webhook ingestion from processing
- S3 for all data persistence (customer data, audio files, processed results)
- CloudFormation for infrastructure as code
- Monorepo with shared library for common code
- Service layer pattern for all external integrations
- Pydantic for all data models and settings management
- Async/await for all I/O operations

## Working with Services

### Development Commands

Each service has its own `pyproject.toml` and dependencies:

```bash
# Navigate to a service directory
cd webhook-handler  # or voice-parser, customer-lookup-server, data-api-server

# Install dependencies
uv sync

# Run linting
uv run ruff check

# Run tests
uv run pytest

# Add new dependency
uv add package-name

# Regenerate requirements.txt for Docker (when adding dependencies)
uv pip compile pyproject.toml -o requirements.txt
```

### Shared Library

The `shared-lib` package is installed as a local dependency in each service's `pyproject.toml`:

```toml
[tool.uv.sources]
ai-voice-shared = { path = "../shared-lib", editable = true }
```

When you modify shared-lib code, changes are immediately available to all services.

## Deployment

All services are deployed as Docker containers to Lambda via ECR. CloudFormation manages all infrastructure.

### Deployment Order

```bash
# 1. Create secrets in AWS Secrets Manager
make secrets-create ENV=dev

# 2. Deploy infrastructure stacks in order
./infrastructure/deploy.sh dev ecr             # ECR repositories
./infrastructure/deploy.sh dev shared          # S3, SQS, API Gateway
./infrastructure/deploy.sh dev customer-lookup # Customer lookup Lambda
./infrastructure/deploy.sh dev voice-parser    # Voice parser Lambda
./infrastructure/deploy.sh dev webhook-handler # Webhook handler Lambda
./infrastructure/deploy.sh dev data-api        # Data API Lambda

# Or deploy all at once
./infrastructure/deploy.sh dev all
```

See [infrastructure/README.md](infrastructure/README.md) for detailed deployment instructions.

### Configuration Management

**Non-Secret Configuration:**
- Stored in `infrastructure/parameters/{env}.json`
- Includes: bucket names, Twilio account SID, phone numbers, Lambda settings
- Safe to commit to git

**Secret Configuration:**
- Stored in AWS Secrets Manager
- Includes: Twilio auth token, OpenAI API key
- Created with `make secrets-create ENV=dev`
- Referenced in CloudFormation via Secret ARNs
- See [infrastructure/SECRETS.md](infrastructure/SECRETS.md)

## S3 Data Organization

All artifacts are stored in S3 with company-based partitioning:

```
{company_id}/{message_intent}/{tag}_{message_id}_{file_type}.{extension}
```

**Message Intents:**
- `job-to-be-done` - Actionable tasks
- `knowledge-document` - Reference information
- `other` - General messages

**File Types:**
- `_audio.ogg` - Original audio recording (voice messages only)
- `_full_text.txt` - Complete transcription or original text
- `_text_summary.txt` - Structured analysis (job-to-be-done and knowledge-document only)

## Testing

The project uses a **three-tier testing strategy**:

### Test Structure

Each service follows this directory structure:

```
{service}/tests/
├── unit/              # Isolated unit tests (fast, no external dependencies)
├── integration/       # Component integration tests (mocked external services)
└── e2e/              # End-to-end tests (requires deployed infrastructure)
```

Plus system-wide tests at the root:

```
tests/e2e/            # Cross-service end-to-end tests
```

### Test Definitions

- **Unit tests** (`tests/unit/`): Test individual functions/classes in complete isolation with all dependencies mocked
- **Integration tests** (`tests/integration/`): Test service components working together with external services (AWS, Twilio, OpenAI) mocked but internal components real
- **Service E2E tests** (`{service}/tests/e2e/`): Test service's external API boundary against real deployed infrastructure
- **System E2E tests** (`tests/e2e/`): Test complete message processing pipeline across multiple services

### Running Tests

```bash
# Pre-deployment testing (no AWS required)
make test-pre-deploy                    # All services: unit + integration
make test-voice-parser-pre-deploy       # Single service: unit + integration

# Per-service testing
make test-voice-parser-unit             # Unit tests only
make test-voice-parser-integration      # Integration tests only
make test-voice-parser-e2e              # Service e2e tests (requires deployed infra)

# Post-deployment verification (requires AWS)
make test-post-deploy                   # All service e2e + system e2e
make test-system-e2e                    # System-wide e2e only

# Direct pytest usage
cd voice-parser
uv run pytest tests/unit -v            # Unit tests
uv run pytest tests/integration -v     # Integration tests
uv run pytest tests/e2e -v             # E2E tests
```

### When to Run Each Test Level

1. **During development**: Run unit tests frequently
2. **Before committing**: Run `make test-pre-deploy` (unit + integration)
3. **After deploying to dev**: Run `make test-post-deploy` (all e2e tests)
4. **Before deploying to prod**: Verify dev deployment passed all post-deploy tests

### Test Markers

All services use pytest markers for test categorization:

```python
@pytest.mark.unit
def test_something_isolated():
    ...

@pytest.mark.integration
def test_components_together():
    ...

@pytest.mark.e2e
def test_deployed_service():
    ...
```

Run specific test types:
```bash
uv run pytest -m unit           # Unit tests only
uv run pytest -m integration    # Integration tests only
uv run pytest -m e2e            # E2E tests only
uv run pytest -m "not e2e"      # All except e2e
```

## Common Development Tasks

### Adding a New Dependency

```bash
cd {service-directory}
uv add package-name
uv pip compile pyproject.toml -o requirements.txt  # For Docker
```

### Updating Shared Library

```bash
cd shared-lib
# Make changes to ai_voice_shared/
uv run ruff check  # Lint
uv run pytest      # Test

# No need to reinstall in services - changes are live (editable install)
```

### Debugging Lambda Functions Locally

Each service has example `.env.example` files. Copy to `.env` and fill in values:

```bash
cd voice-parser
cp .env.example .env
# Edit .env with actual values
uv run python -m voice_parser.worker  # Run locally
```

### Viewing CloudWatch Logs

```bash
aws logs tail /aws/lambda/{function-name} --follow --profile cohesv
```

## Key Design Patterns

1. **Async/Await**: All I/O operations use async/await for efficiency
2. **Service Layer**: External APIs abstracted behind service classes (in `services/` directories)
3. **Pydantic Models**: Type-safe data validation for all payloads and settings
4. **Batch Processing**: voice-parser processes multiple SQS messages per invocation
5. **Partial Failure Handling**: Returns `batchItemFailures` to SQS for automatic retry
6. **Signature Verification**: Twilio signature validation in webhook-handler
7. **Presigned URLs**: data-api-server never proxies files, generates presigned URLs instead
8. **Shared Models**: Common data structures in shared-lib for consistency
