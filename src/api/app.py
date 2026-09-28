"""
FastAPI application setup for Multi-Source Agentic Text-to-SQL with MCP.
Includes CORS middleware and static serving for the interactive frontend/.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import router


def create_app() -> FastAPI:
    """Initializes and configures the FastAPI application instance."""
    application = FastAPI(
        title="Multi-Source Agentic Text-to-SQL with MCP",
        description="An agentic data analyst that converts natural-language questions into safe, multi-source SQL queries and synthesizes results through a custom MCP tool layer.",
        version="0.1.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(router)

    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
    if os.path.isdir(frontend_dir):
        application.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return application


app = create_app()
