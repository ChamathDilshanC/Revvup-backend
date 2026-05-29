from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, bikes
from app.core.config import get_settings

app = FastAPI(
    title="RevvUp API",
    description="Premium motorbike marketplace — serverless FastAPI on Vercel",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bikes.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "revvup-backend",
        "supabase_configured": get_settings().is_configured,
    }
