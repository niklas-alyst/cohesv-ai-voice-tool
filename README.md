# Voice Parser

AI-powered WhatsApp voice note processing service that transcribes and structures voice messages.

## Overview

This service processes WhatsApp voice notes by:
1. Receiving webhooks from WhatsApp via API Gateway
2. Validating webhook signatures and queuing messages to SQS
3. Processing messages asynchronously via Lambda worker
4. Downloading audio files from WhatsApp
5. Storing audio files in S3 for persistence
6. Transcribing using OpenAI Whisper
7. Structuring the transcription using LLM

## Architecture

The system uses a decoupled, queue-based architecture with AWS Lambda functions:

**Webhook Layer:**
- **webhook_verification.py**: Lambda function for Meta webhook verification (GET requests)
- **webhook_handler.py**: Lambda function that validates signatures and enqueues payloads to SQS

**Worker Layer:**
- **worker_handler.py**: Lambda function (Docker) that processes messages from SQS queue

**Data Flow:**
```
WhatsApp → API Gateway → Lambda (webhook_handler)
    → SQS Queue → Lambda Docker (worker_handler)
        → WhatsApp API (download) → S3 (storage)
        → Whisper API (transcription) → LLM API (structuring)
```

## Tech Stack

- **Python 3.13**
- **AWS Lambda**: Serverless compute for webhook handling and workers
- **AWS SQS**: Message queue for decoupling webhook ingestion from processing
- **AWS S3**: Persistent audio file storage
- **AWS API Gateway**: HTTP endpoint for WhatsApp webhooks
- **OpenAI APIs**: Whisper (transcription) and GPT (structuring)
- **Pydantic**: Data validation and models
- **Dependency Management**: uv

## Development

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker
- AWS CLI configured

### Setup

```bash
# Install dependencies
uv sync

# Run linting
uv run ruff check
```

### Environment Variables

Required configuration:

**WhatsApp Configuration:**
- `WHATSAPP_APP_SECRET`: App secret for signature verification
- `WHATSAPP_VERIFY_TOKEN`: Token for webhook verification
- `WHATSAPP_ACCESS_TOKEN`: Access token for API calls

**AWS Configuration:**
- `AWS_REGION`: AWS region
- `SQS_QUEUE_URL`: SQS queue URL for webhook messages
- `S3_BUCKET_NAME`: S3 bucket for audio storage

**OpenAI Configuration:**
- `OPENAI_API_KEY`: OpenAI API key

## Deployment

### Build and Deploy Worker Lambda to ECR

The worker Lambda function is deployed as a Docker container:

```bash
# Build Docker image
make build

# Build and push to ECR
make deploy
```

### Webhook Lambda Functions

The lightweight webhook Lambda functions (`webhook_verification.py` and `webhook_handler.py`) are deployed separately (typically via AWS SAM, Terraform, or similar IaC tools).

### Update Dependencies

When adding new dependencies:

```bash
# Add package
uv add package-name

# Regenerate requirements.txt for Docker
uv pip compile pyproject.toml -o requirements.txt
```

## Project Structure

```
src/
├── voice_parser/              # Main worker package
│   ├── worker_handler.py      # Lambda handler for SQS processing
│   ├── models.py              # Pydantic models for WhatsApp payloads
│   ├── core/
│   │   └── settings.py        # Configuration management
│   └── services/
│       ├── whatsapp_client.py # WhatsApp API client
│       ├── storage.py         # S3 operations
│       ├── transcription.py   # OpenAI Whisper
│       └── llm.py             # OpenAI GPT
└── aws_lambdas/               # Webhook Lambda functions
    ├── webhook_verification.py # GET webhook verification
    └── webhook_handler.py      # POST webhook to SQS
```

## Lambda Functions

### Webhook Handler
- **Purpose**: Receives POST requests from WhatsApp, validates signatures, enqueues to SQS
- **Trigger**: API Gateway (POST /webhook)
- **Response**: Synchronous 200 OK

### Webhook Verification
- **Purpose**: Responds to Meta's webhook verification challenge
- **Trigger**: API Gateway (GET /webhook)
- **Response**: Returns challenge parameter

### Worker Handler
- **Purpose**: Processes voice messages from SQS queue
- **Trigger**: SQS events (batch processing)
- **Deployment**: Docker container via ECR

## License

MIT
