"""FastAPI application: lifespan, routers, entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from telemelya.server.config import settings
from telemelya.server.state import state_manager
from telemelya.server.media import media_manager
from telemelya.server.bot_api import router as bot_api_router
from telemelya.server.control_api import router as control_api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Telemelya server...")
    await state_manager.connect()
    await media_manager.connect()
    logger.info("Connected to Redis and MinIO")
    yield
    logger.info("Shutting down Telemelya server...")
    await media_manager.close()
    await state_manager.close()


app = FastAPI(
    title="Telemelya — Mock Telegram Bot API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(bot_api_router)
app.include_router(control_api_router)


@app.get("/")
async def root():
    return {
        "service": "Telemelya",
        "version": "0.1.0",
        "description": "Mock Telegram Bot API for BDD testing",
    }


def main():
    uvicorn.run(
        "telemelya.server.app:app",
        host=settings.mock_server_host,
        port=settings.mock_server_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
