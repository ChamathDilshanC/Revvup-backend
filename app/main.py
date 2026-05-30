import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, bikes, owner_bikes, showrooms
from app.core.config import get_settings
from app.core.handlers import register_exception_handlers, request_id_middleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="RevvUp API",
    description="Premium motorbike marketplace — serverless FastAPI on Vercel",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

register_exception_handlers(app)
app.middleware("http")(request_id_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bikes.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(owner_bikes.router, prefix="/api/v1")
app.include_router(showrooms.router, prefix="/api/v1")
app.include_router(showrooms.owner_router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")

_API_VERSION = "1.0.0"

_PROJECT_IDEA = {
    "name": "RevvUp",
    "tagline": "Premium motorbike marketplace",
    "summary": (
        "A mobile-first platform where enthusiasts browse premium motorcycles and "
        "verified bike showroom owners list inventory, manage listings (CRUD), and "
        "upload images. Showroom owners register with developer approval before gaining "
        "admin capabilities."
    ),
    "stack": ["React Native (Expo)", "FastAPI", "Supabase", "Vercel"],
    "features": [
        "Public bike catalog with detailed specs",
        "Client vs showroom-owner registration",
        "Developer email approval for showroom owners",
        "Owner/admin bike CRUD and image upload to Supabase Storage",
    ],
}

_DEVELOPER_CONTACT = {
    "name": "Chamath Dilshan",
    "email": "dilshancolonne123@gmail.com",
    "github": "https://github.com/chamathdilshanc",
    "linkedin": "https://www.linkedin.com/in/chamathdilsahnc/",
}


def _health_payload() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "revvup-backend",
        "version": _API_VERSION,
        "environment": "production" if os.getenv("VERCEL") else "development",
        "supabase_configured": settings.is_configured,
        "email_configured": settings.email_configured,
    }


@app.get("/", tags=["default"])
def root(request: Request):
    """API landing page — use this URL to discover docs and key routes."""
    settings = get_settings()
    base = str(request.base_url).rstrip("/")
    return {
        "success": True,
        "service": "revvup-backend",
        "version": _API_VERSION,
        "message": "RevvUp API is running. Explore interactive docs or call the endpoints below.",
        "status": "online",
        "supabase_configured": settings.is_configured,
        "documentation": {
            "swagger_ui": f"{base}/api/docs",
            "openapi_json": f"{base}/api/openapi.json",
        },
        "project": _PROJECT_IDEA,
        "developer": _DEVELOPER_CONTACT,
        "links": {
            "health": f"{base}/api/health",
            "bikes_catalog": f"{base}/api/v1/bikes",
            "owner_bikes": f"{base}/api/v1/owner/bikes",
            "showrooms": f"{base}/api/v1/showrooms",
            "register": f"{base}/api/v1/auth/register",
            "login": f"{base}/api/v1/auth/login",
        },
        "api_prefix": "/api/v1",
    }


@app.get("/api/health", tags=["default"])
@app.get("/health", tags=["default"])
def health():
    """Liveness check for monitors and deploy verification."""
    return _health_payload()
