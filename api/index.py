"""
Vercel serverless entry — exposes the FastAPI ASGI app.
"""
from app.main import app

# Vercel @vercel/python expects a module-level `app` or handler
handler = app
