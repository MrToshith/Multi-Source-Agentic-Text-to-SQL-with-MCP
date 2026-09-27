"""
FastAPI application setup for Multi-Source Agentic Text-to-SQL with MCP.
"""

from fastapi import FastAPI
from src.api.routes import router


def create_app() -> FastAPI:
    """Initializes and configures the FastAPI application instance."""
    application = FastAPI(
        title="Multi-Source Agentic Text-to-SQL with MCP",
        description="An agentic data analyst that converts natural-language questions into safe, multi-source SQL queries and synthesizes results through a custom MCP tool layer.",
        version="0.1.0",
    )
    application.include_router(router)
    return application


app = create_app()
