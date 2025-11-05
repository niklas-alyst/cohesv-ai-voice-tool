"""Data API Server - FastAPI microservice for serving S3 data."""

__version__ = "0.1.0"


def main() -> None:
    """Entry point for running the server locally."""
    import uvicorn

    from .main import app

    uvicorn.run(app, host="0.0.0.0", port=8000)
