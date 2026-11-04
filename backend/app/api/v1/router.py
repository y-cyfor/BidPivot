from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.files import router as files_router
from app.api.v1.bid import router as bid_router
from app.api.v1.projects import router as projects_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.export import router as export_router
from app.api.v1.conversation import router as conversation_router
from app.api.v1.admin import router as admin_router
from app.api.v1.competitors import router as competitors_router
from app.api.v1.loss_analysis import router as loss_analysis_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.ws import ticket_router as ws_ticket_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(bid_router)
router.include_router(files_router)
router.include_router(projects_router)
router.include_router(knowledge_router)
router.include_router(export_router)
router.include_router(conversation_router)
router.include_router(admin_router)
router.include_router(competitors_router)
router.include_router(loss_analysis_router)
router.include_router(dashboard_router)
router.include_router(ws_ticket_router)
