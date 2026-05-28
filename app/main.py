from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, bikes

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


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "revvup-backend"}
