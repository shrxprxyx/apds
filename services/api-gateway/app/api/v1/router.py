from fastapi import APIRouter

from app.api.v1.endpoints import analyse, auth, feedback

api_router = APIRouter()

# Doc endpoints: /analyse, /email/scan, /feedback, /health
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(analyse.router, prefix="/analyse", tags=["analyse"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])