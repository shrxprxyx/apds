from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from contextlib import asynccontextmanager
import asyncio
import json
import structlog

from app.core.config import settings
from app.core.database import init_db
from app.core.redis import init_redis, get_redis
from app.api.v1.router import api_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting api-gateway", environment=settings.ENVIRONMENT)
    await init_db()
    await init_redis()
    yield
    logger.info("shutting down api-gateway")


app = FastAPI(
    title="APDS API Gateway",
    description="Advanced Phishing Detection System — API Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Prometheus ───────────────────────────────────────────────
Instrumentator().instrument(app).expose(app)

# ─── REST Routes ──────────────────────────────────────────────
app.include_router(api_router, prefix=f"/api/{settings.API_VERSION}")


# ─── WebSocket /ws/tasks/{task_id} ────────────────────────────
# Per doc: subscribe to real-time verdict delivery
# Messages: PROCESSING → COMPLETE (with verdict) | TIMEOUT after 30s
@app.websocket("/ws/tasks/{task_id}")
async def websocket_verdict(websocket: WebSocket, task_id: str):
    await websocket.accept()
    redis = await get_redis()

    try:
        await websocket.send_json({"status": "PROCESSING"})

        # Poll Redis for verdict (APDS:VERDICT:{url_hash} keyed by task_id mapping)
        ws_key = f"APDS:WS:TASK:{task_id}"
        timeout = 30
        elapsed = 0

        while elapsed < timeout:
            result = await redis.get(ws_key)
            if result:
                data = json.loads(result)
                await websocket.send_json({"status": "COMPLETE", "verdict": data})
                break
            await asyncio.sleep(0.5)
            elapsed += 0.5

        if elapsed >= timeout:
            await websocket.send_json({"status": "TIMEOUT"})

    except WebSocketDisconnect:
        logger.info("websocket disconnected", task_id=task_id)


# ─── Health ───────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway"}