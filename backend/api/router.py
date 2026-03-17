from fastapi import APIRouter
from backend.api import student, teacher, common, admin, agent

api_router = APIRouter()

api_router.include_router(common.router)
api_router.include_router(student.router)
api_router.include_router(teacher.router)
api_router.include_router(admin.router)
api_router.include_router(agent.router, prefix="/api")