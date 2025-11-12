# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development guidelines
- We use `uv` for this project, so all python code should be ran with `uv run ...`
- You may have to call `uv` directly from the binary: `/home/niklas/.local/bin/uv`
- NEVER modify `pyproject.toml` directly, use the corresponding `uv` commands, e.g. `uv add`
- Run linting after each development: `uv run ruff check`

## Project Overview

This is a WhatsApp AI Assistant built on Python and deployed on AWS Lambda. The system uses a decoupled, queue-based architecture for processing voice notes. The core consists of:

1. **Webhook Lambda functions** - Lightweight functions for webhook verification and SQS enqueueing
2. **Worker Lambda function** - Docker-based Lambda that processes voice messages from SQS

## Architecture

### Webhook Layer

Two lightweight Lambda functions handle incoming WhatsApp webhooks:

**webhook_verification.py**
- Handles GET requests from Meta for webhook verification
- Validates verify token and returns challenge value
- Triggered by: API Gateway GET /webhook

**webhook_handler.py**
- Handles POST requests containing WhatsApp events
- Verifies X-Hub-Signature-256 using HMAC SHA256
- Enqueues valid payloads to SQS
- Returns immediate 200 OK response to WhatsApp
- Triggered by: API Gateway POST /webhook

### Worker Layer

**worker_handler.py**
- AWS Lambda function deployed as Docker container
- Polls SQS queue for webhook messages
- Processes voice messages through full pipeline:
  1. Parse WhatsApp webhook payload
  2. Download audio from WhatsApp temporary URL
  3. Upload to S3 for persistence
  4. Transcribe using OpenAI Whisper
  5. Structure transcription using LLM
  6. Save results (database TBD)

The worker uses batch processing with partial failure handling, returning `batchItemFailures` to SQS for automatic retry.

### Data Flow

```
WhatsApp → API Gateway → webhook_handler Lambda
    → SQS Queue → worker_handler Lambda (Docker)
        → WhatsApp API (download audio)
        → S3 (persist audio)
        → Whisper API (transcribe)
        → LLM API (structure)
        → Database (save results)
```

## Package Structure

```
src/
├── voice_parser/              # Main worker package (Docker Lambda)
│   ├── __init__.py           # Package version
│   ├── worker_handler.py     # Lambda handler for SQS events
│   ├── models.py             # Pydantic models for WhatsApp payloads
│   ├── core/
│   │   ├── __init__.py
│   │   └── settings.py       # Pydantic settings management
│   └── services/             # External service clients
│       ├── __init__.py
│       ├── whatsapp_client.py # WhatsApp Graph API client
│       ├── storage.py         # AWS S3 operations
│       ├── transcription.py   # OpenAI Whisper client
│       └── llm.py             # OpenAI GPT client
└── aws_lambdas/              # Webhook Lambda functions (lightweight)
    ├── webhook_verification.py # GET webhook verification
    └── webhook_handler.py      # POST webhook to SQS
```

**Key architectural decisions:**
- Lambda-based serverless architecture (no EC2/ECS)
- Worker deployed as Docker container via ECR
- Webhook Lambdas are lightweight (no heavy dependencies)
- Service layer pattern for external integrations
- Configuration management with Pydantic Settings
- Pydantic models for data validation

## Development Commands

```bash
# Install dependencies
uv sync

# Install package in editable mode (for local development)
uv pip install -e .

# Run linting
uv run ruff check

# Add new dependency
uv add package-name

# Regenerate requirements.txt for Docker
uv pip compile pyproject.toml -o requirements.txt
```

## Deployment

### Worker Lambda (Docker)

The worker Lambda is containerized and deployed via ECR:

```bash
# Build Docker image
make build

# Build and push to ECR
make deploy
```

**Dockerfile details:**
- Base image: `public.ecr.aws/lambda/python:3.13`
- Dependencies: Installed via pip from `requirements.txt`
- Package: Installed with `pip install --no-deps .`
- Entry point: `voice_parser.worker_handler.lambda_handler`

### Webhook Lambdas

The webhook Lambda functions are deployed separately (typically via IaC tools like AWS SAM, Terraform, or CDK) as they are lightweight and don't require Docker containers.

## Environment Variables

**WhatsApp Configuration:**
- `WHATSAPP_APP_SECRET` - App secret for signature verification
- `WHATSAPP_VERIFY_TOKEN` - Token for webhook verification
- `WHATSAPP_ACCESS_TOKEN` - Access token for API calls
- `WHATSAPP_PHONE_NUMBER_ID` - Phone number ID for API calls

**AWS Configuration:**
- `AWS_REGION` - AWS region
- `SQS_QUEUE_URL` - SQS queue URL for webhook messages
- `S3_BUCKET_NAME` - S3 bucket name for audio storage

**OpenAI Configuration:**
- `OPENAI_API_KEY` - OpenAI API key for Whisper and GPT

## Storage - AWS S3

Audio files are stored in S3 immediately after download from WhatsApp. This ensures data persistence even if downstream processing fails. The worker can retry processing using the S3-stored file.

File naming: `{media_id}.ogg`

## Testing

The project uses pytest for testing:

```bash
# Run tests
uv run pytest

# Run specific test file
uv run pytest tests/test_storage.py
```

## Key Design Patterns

1. **Async/Await**: All I/O operations use async/await for efficiency
2. **Service Layer**: External APIs abstracted behind service classes
3. **Pydantic Models**: Type-safe data validation for WhatsApp payloads
4. **Batch Processing**: Worker processes multiple SQS messages per invocation
5. **Partial Failure Handling**: Returns `batchItemFailures` for automatic retry
6. **Signature Verification**: HMAC SHA256 validation for webhook security
