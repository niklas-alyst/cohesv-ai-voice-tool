"""FastAPI application for Data API Server."""

import logging
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from ai_voice_shared.models import S3ListResponse
from ai_voice_shared.services.s3_service import S3Service
from ai_voice_shared.settings import S3Settings
from .settings import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize settings
settings = Settings()

# Initialize S3 settings from general settings
s3_settings = S3Settings(
    aws_region=settings.aws_region,
    s3_bucket_name=settings.s3_bucket_name,
    aws_profile=settings.aws_profile,
)

# Initialize FastAPI app
app = FastAPI(
    title="Data API Server",
    description="API for accessing S3-stored voice message data",
    version="0.1.0",
)

# Initialize S3 service
s3_service = S3Service(s3_settings)


# Middleware for API key validation (for local testing)
# In production, API Gateway handles this
@app.middleware("http")
async def validate_api_key(request: Request, call_next):
    """Validate API key if configured."""
    # Skip validation for health check
    if request.url.path == "/health":
        return await call_next(request)

    # Only validate if API key is configured (for local testing)
    if settings.api_key:
        api_key = request.headers.get("x-api-key")
        if not api_key or api_key != settings.api_key:
            return JSONResponse(
                status_code=403,
                content={"message": "Forbidden"},
            )

    return await call_next(request)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/files/list", response_model=S3ListResponse)
async def list_files(
    company_id: str = Query(..., description="Company identifier"),
    message_intent: str = Query(
        ...,
        description="Message intent: job-to-be-done, knowledge-document, or other",
    ),
    nextContinuationToken: str | None = Query(
        None,
        description="Continuation token from previous response for pagination",
    ),
) -> S3ListResponse:
    """
    List files stored in S3 for a specific company and message intent.

    This endpoint provides paginated access to files in the S3 bucket,
    filtered by company_id and message_intent.

    Args:
        company_id: Company identifier for filtering
        message_intent: Message intent type (job-to-be-done, knowledge-document, other)
        nextContinuationToken: Optional pagination token from previous response

    Returns:
        S3ListResponse containing:
        - files: Array of S3ObjectMetadata (key, etag, size, last_modified)
        - nextContinuationToken: Token for next page (null if no more pages)

    Raises:
        HTTPException: 500 if S3 operation fails
    """
    # Validate message_intent
    valid_intents = ["job-to-be-done", "knowledge-document", "other"]
    if message_intent not in valid_intents:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid message_intent. Must be one of: {', '.join(valid_intents)}",
        )

    try:
        result = await s3_service.list_objects(
            company_id=company_id,
            message_intent=message_intent,
            continuation_token=nextContinuationToken,
        )
        return result
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/files/get-download-url")
async def get_download_url(
    key: str = Query(..., description="S3 object key (URL-encoded)"),
) -> dict[str, str]:
    """
    Generate a presigned URL for downloading a file from S3.

    This endpoint generates a short-lived (5 minute) presigned URL that allows
    direct download from S3 without going through the Lambda function.

    Args:
        key: S3 object key (must be URL-encoded)

    Returns:
        Dictionary containing the presigned URL

    Raises:
        HTTPException: 404 if file not found, 500 for other errors
    """
    # URL-decode the key
    decoded_key = unquote(key)

    try:
        url = await s3_service.generate_presigned_url(decoded_key)
        return {"url": url}
    except ValueError:
        # Object not found
        logger.warning(f"File not found: {decoded_key}")
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error(f"Error generating presigned URL: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Lambda handler
# Mangum wraps the FastAPI app to make it compatible with AWS Lambda
# api_gateway_base_path strips the stage name from the path so FastAPI sees /files/list instead of /dev/files/list
handler = Mangum(app, lifespan="off", api_gateway_base_path=f"/{settings.environment}")
