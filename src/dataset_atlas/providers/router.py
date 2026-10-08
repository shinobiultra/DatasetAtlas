"""Mount this router under /api/v1 in the workbench service."""
from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .schemas import ContextRequest, ConversationRequest, ProviderConfig
from .service import ProviderService


def _mutation_guard(request: Request) -> None:
    if request.headers.get("X-Atlas-Request") != "1":
        raise HTTPException(status_code=403, detail="X-Atlas-Request: 1 required")
    origin = request.headers.get("Origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme != request.url.scheme or parsed.netloc.lower() != request.url.netloc.lower():
            raise HTTPException(status_code=403, detail="cross-origin request rejected")


def create_provider_router(service: ProviderService) -> APIRouter:
    router = APIRouter(tags=["providers"])

    @router.get("/providers")
    def list_providers():
        return service.list_providers()

    @router.post("/providers", dependencies=[Depends(_mutation_guard)])
    def configure_provider(config: ProviderConfig):
        return service.put_provider(config)

    @router.post("/providers/{provider_id}/probe", dependencies=[Depends(_mutation_guard)])
    def probe_provider(provider_id: str):
        try:
            return service.probe(provider_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/conversations/context", dependencies=[Depends(_mutation_guard)])
    def preview_context(request: ContextRequest):
        try:
            return service.preview(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/conversations", dependencies=[Depends(_mutation_guard)])
    def converse(request: ConversationRequest):
        try:
            return service.converse(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/conversations")
    def list_conversations(limit: int = Query(default=100, ge=1, le=1000)):
        return service.list_conversations(limit)

    @router.post('/conversation-jobs', dependencies=[Depends(_mutation_guard)])
    def start_conversation_job(request: ConversationRequest):
        try:
            return service.start_conversation_job(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get('/conversation-jobs')
    def list_conversation_jobs(limit: int = Query(default=100, ge=1, le=100)):
        return service.list_conversation_jobs(limit)

    @router.get('/conversation-jobs/{job_id}')
    def conversation_job(job_id: str):
        try:
            return service.get_conversation_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail='model request not found') from exc

    @router.post('/conversation-jobs/{job_id}/cancel', dependencies=[Depends(_mutation_guard)])
    def cancel_conversation_job(job_id: str):
        try:
            return service.cancel_conversation_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail='model request not found') from exc

    @router.get("/conversations/{conversation_id}")
    def get_conversation(conversation_id: str):
        try:
            return service.get_conversation(conversation_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="conversation not found") from exc

    @router.get("/conversation-batches/{batch_id}")
    def get_conversation_batch(batch_id: str):
        try:
            return service.get_batch(batch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="conversation batch not found") from exc

    return router
