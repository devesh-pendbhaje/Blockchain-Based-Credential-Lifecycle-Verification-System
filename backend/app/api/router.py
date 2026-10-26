from fastapi import APIRouter
from app.api.routes import issuers, credentials, documents, merkle, challenges, presentations, auth

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(issuers.router)
api_router.include_router(credentials.router)
api_router.include_router(documents.router)
api_router.include_router(merkle.router)
api_router.include_router(challenges.router)
api_router.include_router(presentations.router)
