from fastapi import APIRouter
from . import auth, application

router = APIRouter(prefix="/portal", tags=["portal"])

router.include_router(auth.router)
router.include_router(application.router)