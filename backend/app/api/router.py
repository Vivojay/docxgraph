from fastapi import APIRouter

from backend.app.api.routes import auth, cases, match, admin

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(cases.router)
api_router.include_router(match.router)
api_router.include_router(admin.router)
