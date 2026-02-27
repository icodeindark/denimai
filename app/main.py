# app/main.py
from fastapi import FastAPI, Request
from app.api.webhook import router as webhook_router
from app.models.database import init_db

app = FastAPI(title="DenimAI Backend")

# ── Initialize database on startup ───────────────────────────────────────────
# Creates tables if they don't exist yet.
# Safe to run every time — it checks before creating.
@app.on_event("startup")
async def startup_event():
    print("🚀 DenimAI starting up...")
    init_db()
    print("🏪 Store database ready.")

# ── Register routes ───────────────────────────────────────────────────────────
app.include_router(webhook_router)

# ── Request logger middleware ─────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"DEBUG: {request.method} {request.url.path}")
    response = await call_next(request)
    return response

@app.get("/")
async def root():
    return {"status": "online", "message": "DenimAI is running"}