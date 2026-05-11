"""
YahavisAI Backend - FastAPI Application Entry Point
Production-ready Yahavis AI Operating System Backend
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings, get_cors_origins
from app.core.logging import setup_logging
from app.core.security import setup_rate_limiting
from app.db.supabase_client import init_supabase, close_supabase
from app.api.websocket.agent_socket import websocket_router
from app.api.v1.routes import auth, chat, tasks, workflows, automations, devices

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize database
    await init_supabase()
    logger.info("✅ Database connected")
    
    # Initialize task queue
    from app.services.queue.task_queue import init_queue
    await init_queue()
    logger.info("✅ Task queue initialized")
    
    # Start background tasks
    from app.services.automation.workflow_engine import start_workflow_scheduler
    asyncio.create_task(start_workflow_scheduler())
    logger.info("✅ Workflow scheduler started")
    
    logger.info(f"🎯 {settings.APP_NAME} is ready at http://{settings.HOST}:{settings.PORT}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down...")
    await close_supabase()
    logger.info("👋 Goodbye!")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Yahavis AI Operating System Backend - Jarvis-like assistant with cross-platform automation",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"]
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again."
        }
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


# API version prefix
api_v1_prefix = "/api/v1"

# Include routers
app.include_router(auth.router, prefix=f"{api_v1_prefix}/auth", tags=["Authentication"])
app.include_router(chat.router, prefix=f"{api_v1_prefix}/chat", tags=["Chat"])
app.include_router(tasks.router, prefix=f"{api_v1_prefix}/tasks", tags=["Tasks"])
app.include_router(workflows.router, prefix=f"{api_v1_prefix}/workflows", tags=["Workflows"])
app.include_router(automations.router, prefix=f"{api_v1_prefix}/automations", tags=["Automations"])
app.include_router(devices.router, prefix=f"{api_v1_prefix}/devices", tags=["Devices"])

# WebSocket router (no prefix for WebSocket connections)
app.include_router(websocket_router, prefix="/ws")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API info"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Yahavis AI Operating System Backend",
        "docs": "/docs" if settings.DEBUG else None,
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS if not settings.DEBUG else 1,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
