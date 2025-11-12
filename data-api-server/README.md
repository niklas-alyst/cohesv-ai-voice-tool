# Data API Server

A FastAPI-based microservice for serving S3-stored voice message data via a secure REST API. This service acts as a secure "file server," abstracting the S3 bucket from client applications and providing authenticated access to structured voice message data.

## Overview

This API provides paginated access to voice message files stored in S3, organized by company ID and message intent. It generates presigned URLs for secure, direct downloads from S3 without routing large files through Lambda.

### Architecture

- **Framework**: FastAPI with Mangum adapter for AWS Lambda
- **Deployment**: Docker container on AWS Lambda behind API Gateway
- **Authentication**: API key validation via AWS API Gateway
- **Storage**: AWS S3 for file persistence

### S3 Data Structure

Files are organized in S3 with the following structure:

```
{company_id}/{message_intent}/{tag}_{message_id}_{file_type}.{extension}
```

**Message Intents:**
- `job-to-be-done` - Action items and tasks
- `knowledge-document` - Documentation and information
- `other` - General messages

**File Types:**
- `_audio.ogg` - Original audio recording (if audio message)
- `_full_text.txt` - Complete transcription or original text
- `.text_summary.txt` - Structured analysis (for job-to-be-done and knowledge-document only)

## API Endpoints

### Authentication

All endpoints require an API key passed as a header:

```
x-api-key: YOUR_SECRET_API_KEY
```

### 1. List Files

List files stored in S3 for a specific company and message intent.

**Endpoint:** `GET /files/list`

**Query Parameters:**
- `company_id` (required) - Company identifier
- `message_intent` (required) - Message intent: `job-to-be-done`, `knowledge-document`, or `other`
- `nextContinuationToken` (optional) - Pagination token from previous response

**Response (200 OK):**
```json
{
  "files": [
    {
      "key": "company123/job-to-be-done/bathroom-renovation_SM1234567890_audio.ogg",
      "etag": "\"a1b2c3d4e5f67890abcdef123456789\"",
      "size": 123456,
      "last_modified": "2025-11-05T14:30:01Z"
    },
    {
      "key": "company123/job-to-be-done/bathroom-renovation_SM1234567890_full_text.txt",
      "etag": "\"b2c3d4e5f67890abcdef123456789a1\"",
      "size": 1024,
      "last_modified": "2025-11-05T14:30:02Z"
    }
  ],
  "nextContinuationToken": "1YETG/Clv4kQ...An/R+h4d="
}
```

**Notes:**
- Returns up to 1000 files per request
- If `nextContinuationToken` is `null`, there are no more pages
- The `etag` is critical for change detection

**Example Usage:**
```bash
curl -X GET "https://api.example.com/files/list?company_id=company123&message_intent=job-to-be-done" \
  -H "x-api-key: YOUR_API_KEY"
```

### 2. Get Download URL

Generate a presigned URL for downloading a file directly from S3.

**Endpoint:** `GET /files/get-download-url`

**Query Parameters:**
- `key` (required) - S3 object key (must be URL-encoded)

**Response (200 OK):**
```json
{
  "url": "https://your-bucket.s3.your-region.amazonaws.com/..."
}
```

**Error Response (404 Not Found):**
```json
{
  "message": "File not found"
}
```

**Notes:**
- The presigned URL expires after 5 minutes
- The API validates file existence before generating the URL
- Clients should use the URL immediately to download the file

**Example Usage:**
```bash
# Get download URL
curl -X GET "https://api.example.com/files/get-download-url?key=company123%2Fjob-to-be-done%2Fbathroom-renovation_SM1234567890_audio.ogg" \
  -H "x-api-key: YOUR_API_KEY"
```

### 3. Health Check

Simple health check endpoint (no authentication required).

**Endpoint:** `GET /health`

**Response (200 OK):**
```json
{
  "status": "healthy"
}
```

## Development

### Prerequisites

- Python 3.13+
- uv - Python package manager
- Docker (for containerized deployment)
- AWS CLI configured with appropriate credentials

### Setup

1. **Install dependencies:**
   ```bash
   cd data-api-server
   uv sync
   ```

2. **Configure environment variables:**
   Create a `.env` file based on `.env.example`

3. **Run locally:**
   ```bash
   uv run uvicorn data_api_server.main:app --reload
   ```
   The server will start on `http://localhost:8000`

### Development Commands

```bash
# Install dependencies
uv sync

# Add new dependency
uv add package-name

# Regenerate requirements.txt for Docker
uv pip compile pyproject.toml -o requirements.txt

# Run linting
uv run ruff check

# Run tests
uv run pytest

# Run locally
uv run uvicorn data_api_server.main:app --reload
```

## Deployment

From the project root directory:

```bash
# Build and deploy
make deploy-data-api

# Or build only
make build-data-api

# Or update Lambda function only (after initial deployment)
make update-data-api-lambda
```

## Project Structure

```
data-api-server/
├── src/
│   └── data_api_server/
│       ├── __init__.py          # Package init
│       ├── main.py              # FastAPI app with endpoints and Lambda handler
│       └── settings.py          # Pydantic settings for configuration
├── tests/                       # Test suite
│   ├── test_api.py             # API endpoint tests
│   └── test_middleware.py      # Middleware tests
├── Dockerfile                   # Docker build for Lambda deployment
├── pyproject.toml              # Project dependencies and metadata
├── requirements.txt            # Generated requirements for Docker
├── README.md                   # This file
└── .env                        # Environment variables (not in git)
```

## Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `AWS_REGION` | No | AWS region for S3 operations | `ap-southeast-2` |
| `S3_BUCKET_NAME` | Yes | S3 bucket name | - |
| `AWS_PROFILE` | No | AWS profile for credentials (local dev) | None |
| `API_KEY` | No | API key for local testing | None |

## Security Considerations

1. **API Key Authentication**: Managed by AWS API Gateway in production
2. **Presigned URL Expiration**: URLs expire after 5 minutes
3. **File Existence Check**: Validates files exist before generating presigned URLs
4. **No Direct File Access**: Clients download directly from S3 using presigned URLs
5. **Scoped Access**: Only allows access to files within specified company_id/message_intent paths

## Troubleshooting

### Common Issues

1. **403 Forbidden**
   - Check API key is correctly set in `x-api-key` header
   - Verify API Gateway API key configuration

2. **404 File Not Found**
   - Verify the file exists in S3
   - Check the key is correctly URL-encoded
   - Ensure company_id and message_intent match S3 structure

3. **500 Internal Server Error**
   - Check Lambda CloudWatch logs
   - Verify IAM permissions for S3 access
   - Confirm environment variables are set correctly
