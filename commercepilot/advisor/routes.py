from fastapi import APIRouter, HTTPException

from ..runtime import get_advisor_store, get_store
from . import service
from .models import ChatRequest, SessionRequest

router = APIRouter(prefix="/api/advisor", tags=["AI business advisor"])


@router.post("/session")
def session(payload: SessionRequest):
    workspace, conversations = get_store(), get_advisor_store()
    project = service.project_context(workspace, payload.project_id)
    token = payload.session_token or conversations.create(payload.project_id)
    _, data = conversations.read(token, payload.project_id, check_project=True)
    return service.snapshot(token, data, project)


@router.post("/chat")
def chat(payload: ChatRequest):
    if not payload.message.strip() and payload.profile_updates is None and payload.confirmed_action is None:
        raise HTTPException(422, "Write a message or provide planning details to continue.")
    return service.converse(get_store(), get_advisor_store(), payload)
