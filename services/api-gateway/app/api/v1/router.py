from fastapi import APIRouter

from app.api.v1.endpoints import scan, auth, feedback

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(scan.router, prefix="/scan", tags=["scan"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])