# AI Voice Tool

AI-powered WhatsApp assistant that processes voice and text messages, extracting actionable items and knowledge documents for business use.

## Overview

This platform receives WhatsApp messages (voice or text) via Twilio, processes them through AI services to understand intent and structure the content, and stores the results in S3. A REST API provides authenticated access to the processed data.

### Key Features

- **WhatsApp Integration**: Receives voice and text messages via Twilio
- **AI Processing**: Transcribes voice messages and analyzes content to identify:
  - Job-to-be-done (actionable tasks)
  - Knowledge documents (information for reference)
  - Other general messages
- **Structured Output**: LLM-powered analysis structures messages into predefined formats
- **Secure Storage**: All artifacts stored in S3 with company-based partitioning
- **REST API**: Authenticated access to processed data with presigned download URLs

## Architecture

The system consists of four microservices deployed as containerized AWS Lambda functions:

### 1. Webhook Handler ([webhook-handler/](webhook-handler/))
Entry point for incoming Twilio webhooks.
- Validates Twilio signature (`X-Twilio-Signature`)
- Checks sender authorization via customer-lookup service
- Enqueues validated payloads to SQS

### 2. Voice Parser ([voice-parser/](voice-parser/))
Asynchronous worker that processes messages from SQS.
- Downloads voice messages from Twilio
- Transcribes audio using OpenAI Whisper
- Analyzes content using LLM to determine intent and structure
- Uploads artifacts to S3
- Sends feedback to users via WhatsApp

### 3. Customer Lookup Server ([customer-lookup-server/](customer-lookup-server/))
Internal API for customer metadata retrieval.
- Loads customer data from S3 (`customers.json`)
- Provides authorization and company_id for data partitioning
- Invoked by webhook-handler and voice-parser

### 4. Data API Server ([data-api-server/](data-api-server/))
FastAPI-based REST API for accessing processed data.
- Lists files by company and message intent
- Generates presigned S3 URLs for downloads
- API key authentication via API Gateway

### Supporting Infrastructure ([infrastructure/](infrastructure/))
CloudFormation templates for all AWS resources:
- ECR repositories for container images
- S3 bucket for data storage
- SQS queue (with DLQ) for message processing
- HTTP API Gateways for webhook and data API endpoints
- IAM roles and permissions

### Shared Library ([shared-lib/](shared-lib/))
Common code shared across services:
- Pydantic models (e.g., `TwilioWebhookPayload`, `CustomerMetadata`)
- S3 service client
- Customer lookup client
- Shared settings and utilities

## Data Flow

```
Twilio (WhatsApp) → API Gateway → Webhook Handler
    → Customer Lookup (authorization)
    → SQS Queue → Voice Parser
        → Customer Lookup (metadata)
        → Twilio API (download media)
        → OpenAI Whisper (transcribe)
        → OpenAI GPT (analyze & structure)
        → S3 (store artifacts)
        → Twilio API (send feedback)

Client Application → API Gateway → Data API Server
    → S3 (list files, presigned URLs)
```

## S3 Data Organization

Files are organized by company and message intent:

```
{company_id}/{message_intent}/{tag}_{message_id}_{file_type}.{ext}
```

**Message Intents:**
- `job-to-be-done` - Action items and tasks
- `knowledge-document` - Documentation and information
- `other` - General messages

**File Types:**
- `_audio.ogg` - Original audio recording
- `_full_text.txt` - Complete transcription or original text
- `_text_summary.txt` - Structured analysis (job-to-be-done and knowledge-document only)

## Tech Stack

- **Python 3.13** - All services
- **uv** - Package and dependency management
- **AWS Lambda** - Serverless compute (Docker containers)
- **AWS SQS** - Message queue for decoupling
- **AWS S3** - Data persistence
- **AWS API Gateway** - HTTP endpoints
- **Twilio** - WhatsApp messaging integration
- **OpenAI APIs** - Whisper (transcription) and GPT (LLM)
- **FastAPI** - REST API framework (data-api-server)
- **Pydantic** - Data validation and settings management
- **CloudFormation** - Infrastructure as Code

## Project Structure

```
ai-voice-tool/
├── webhook-handler/           # Twilio webhook receiver
├── voice-parser/              # Message processing worker
├── customer-lookup-server/    # Customer metadata API
├── data-api-server/           # REST API for data access
├── shared-lib/                # Common code and models
├── infrastructure/            # CloudFormation templates
│   ├── ecr/                   # Container registry
│   ├── shared/                # S3, SQS, API Gateways
│   ├── customer-lookup-server/
│   ├── voice-parser/
│   ├── webhook-handler/
│   ├── data-api-server/
│   └── parameters/            # Environment-specific config
├── CLAUDE.md                  # AI assistant guidance
└── README.md                  # This file
```

## Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker
- AWS CLI configured with appropriate credentials
- AWS Account ID and region configured

### Development Setup

Each microservice has its own dependencies. Navigate to the service directory:

```bash
# Example: Setting up voice-parser
cd voice-parser
uv sync
uv run ruff check
uv run pytest
```

See individual service README files for detailed setup instructions.

#### Dependency management & shared libraries

- Local development relies on `uv` workspaces so that `shared-lib` (`ai-voice-shared`) is installed in **editable** mode. Running `uv sync` from a service directory uses the `[tool.uv.sources]` configuration in that service’s `pyproject.toml` to point back to `../shared-lib`.
- Docker builds (and any non-`uv` environments) stick to plain `pip` + `requirements*.txt`. Each service exposes a `requirements.deploy.txt` that mirrors `requirements.txt` but replaces the editable shared-lib entry with `ai-voice-shared @ file:///var/task/shared-lib`.
- Refresh both files with `make requirements-sync` (or `make requirements-sync-<service>`). The target runs `uv pip compile`, copies the output to the deploy file, and rewrites the shared-lib entry.
- Dockerfiles must copy `shared-lib/` into the image **before** installing the deploy requirements so the `file:///var/task/shared-lib` reference resolves cleanly.

### Deployment

Deployment uses CloudFormation and must be done in order:

```bash
# 1. Create secrets in AWS Secrets Manager
make secrets-create ENV=dev

# 2. Deploy all infrastructure (including ECR, shared resources, and all services)
# This command will deploy ECR repositories, shared resources, build and push Docker images,
# and then deploy each Lambda service.
make deploy-infra ENV=dev

# Or deploy individual components in order:
# 2a. Deploy ECR repositories
make deploy-ecr ENV=dev
# 2b. Deploy shared infrastructure (S3, SQS, API Gateway)
make deploy-shared ENV=dev
# 2c. Build, push, and deploy individual Lambda services
make deploy-customer-lookup ENV=dev
make deploy-voice-parser ENV=dev
make deploy-webhook-handler ENV=dev
make deploy-data-api ENV=dev
```

See [infrastructure/README.md](infrastructure/README.md) for detailed deployment instructions.

## Configuration

### Non-Secret Parameters
Stored in `infrastructure/parameters/{env}.json`:
- Environment name
- S3 bucket names
- Twilio phone numbers
- Lambda timeouts and memory settings

### Secret Parameters
Managed via AWS Secrets Manager:
- Twilio account SID
- Twilio auth token
- OpenAI API key

See [infrastructure/SECRETS.md](infrastructure/SECRETS.md) for secrets management.

## Development Guidelines

- Use `uv` for all Python operations: `uv run pytest`, `uv add package-name`
- Never modify `pyproject.toml` directly - use `uv` commands
- Run linting after changes: `uv run ruff check`
- All services use async/await for I/O operations
- Follow the service layer pattern for external integrations
- Use Pydantic models for all data validation

## Documentation

Each microservice is thoroughly documented:
- [webhook-handler/README.md](webhook-handler/README.md)
- [voice-parser/README.md](voice-parser/README.md)
- [customer-lookup-server/README.md](customer-lookup-server/README.md)
- [data-api-server/README.md](data-api-server/README.md)
- [shared-lib/README.md](shared-lib/README.md)
- [infrastructure/README.md](infrastructure/README.md)

## Testing

The project uses a three-tier testing strategy:

### Test Structure

```
tests/
├── unit/              # Isolated unit tests (fast, no external dependencies)
├── integration/       # Component integration tests (mocked external services)
└── e2e/              # End-to-end tests (requires deployed infrastructure)
```

- **Unit tests**: Test individual functions/classes in isolation with all dependencies mocked
- **Integration tests**: Test service components working together with external services mocked
- **E2E tests**: Test against real deployed AWS infrastructure

### Running Tests

```bash
# Pre-deployment: Run all unit + integration tests (no AWS required)
make test-pre-deploy

# Post-deployment: Run all service e2e + system-wide e2e tests
make test-post-deploy

# Per-service testing
make test-voice-parser-unit            # Unit tests only
make test-voice-parser-integration     # Integration tests only
make test-voice-parser-e2e             # Service e2e tests
make test-voice-parser-pre-deploy      # Unit + integration

# System-wide e2e test (full pipeline)
make test-system-e2e
```

See individual service README files for service-specific test details.

## Deployment Workflow

Follow this workflow to deploy to dev and then promote to production:

### 1. Pre-Deployment Quality Gates

```bash
# Run linting
make lint

# Run all pre-deployment tests (unit + integration)
make test-pre-deploy
```

These tests run locally without requiring AWS infrastructure.

### 2. Deploy to Dev Environment

```bash
# Deploy all infrastructure to dev. This includes deploying ECR, shared resources,
# building and pushing Docker images, and deploying each Lambda service.
make deploy-infra ENV=dev

# Or deploy individual components in the following order:
# 1. Deploy ECR repositories
make deploy-ecr ENV=dev
# 2. Deploy shared infrastructure (S3, SQS, API Gateway)
make deploy-shared ENV=dev
# 3. Build, push, and deploy individual Lambda services
make deploy-customer-lookup ENV=dev
make deploy-voice-parser ENV=dev
make deploy-webhook-handler ENV=dev
make deploy-data-api ENV=dev
```

### 3. Post-Deployment Verification

```bash
# Run all e2e tests (service-level + system-wide)
make test-post-deploy
```

This runs:
- Service-level e2e tests (testing each service's API boundary)
- System-wide e2e tests (testing the complete message processing pipeline)

**Note**: System-wide e2e tests may incur AWS costs (~$0.10-0.20 per run) due to OpenAI API usage.

### 4. Deploy to Production

Once dev deployment is verified:

```bash
# Deploy to production
make deploy-infra ENV=prod
```

### Deployment Prerequisites

Before deploying, ensure:

1. **Secrets are created** in AWS Secrets Manager:
   ```bash
   make secrets-create ENV=dev
   ```

2. **Parameter files are configured** in `infrastructure/parameters/{env}.json`

3. **AWS credentials are configured** with appropriate permissions

See [infrastructure/README.md](infrastructure/README.md) for detailed deployment instructions.

## License

MIT
