from fastapi import FastAPI

from voice_parser.api.routes.health import router as health_router
from voice_parser.api.routes.webhook import router as webhook_router

app = FastAPI(title="Voice Parser", version="0.1.0")

app.include_router(health_router)
app.include_router(webhook_router)


def main() -> None:
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)