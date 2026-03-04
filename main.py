import time

from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.routes import admin, auth, manager, owner
from app.core.config import get_settings
from app.db.supabase_client import get_supabase_client
from app.telemetries.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan hook.
    Mirrors the pattern in milli_ai_backend by doing startup initialization
    and clean shutdown logging in a single async context manager.
    """
    settings = get_settings()
    # Warm up Supabase client so first request is fast
    _ = get_supabase_client()
    logger.info(
        "startup",
        message="Vami Surat backend starting up",
        supabase_url=settings.supabase_url,
    )
    try:
        yield
    finally:
        logger.info("shutdown", message="Vami Surat backend shutting down")


app = FastAPI(
    title="Vami Surat Pump Management API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)


# Middleware
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", settings.supabase_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """
    Simple health check endpoint, similar to milli_ai_backend.
    """
    try:
        # Touch Supabase client to verify config is at least loadable
        _ = get_supabase_client()
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "timestamp": time.time(),
                "service": "vami-backend",
                "version": "1.0.0",
            },
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("health", message="Health check failed", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": time.time(),
                "error": str(exc),
            },
        )


@app.get("/")
async def root():
    """
    Root endpoint mirroring milli_ai_backend style.
    """
    return JSONResponse(
        content={
            "message": "Vami Surat Backend is running",
            "status": "ok",
            "health_check": "/health",
        }
    )


# Routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(owner.router)
app.include_router(manager.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

