from fastapi import APIRouter
from .search import router as search_router
from .rank import router as rank_router
from .book import router as book_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(search_router, tags=["search"])
api_router.include_router(rank_router, tags=["rank"])
api_router.include_router(book_router, tags=["book"])
