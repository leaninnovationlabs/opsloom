from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.api.assistant.services import AssistantService
from backend.api.assistant.repository import AssistantRepository
from backend.api.assistant.models import (
    Assistant,
    AssistantList,
    AssistantDeletion
)
from backend.util.auth_utils import validate_user, TokenData
import logging
from backend.util.domain_utils import extract_subdomain
from backend.util.database import get_async_session 
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=Assistant)
async def create_assistant(
    assistant: Assistant,
    current_user: TokenData = Depends(validate_user),
    db_session: AsyncSession = Depends(get_async_session)
):
    service = AssistantService(repository=AssistantRepository(db_session))
    created = await service.create_assistant(assistant)
    if not created:
        raise HTTPException(status_code=400, detail="Failed to create Assistant")
    return created

# need response_model_by_alias or else the returned JSON will ALAWAYS use whatever alias is set for the field in the pydantic model
@router.get("", response_model=AssistantList, response_model_by_alias=True)
async def list_assistants(
    request: Request,
    current_user: TokenData = Depends(validate_user),
    session: AsyncSession = Depends(get_async_session)
):
    service = AssistantService(repository=AssistantRepository(session))
    account_short_code = extract_subdomain(request)
    return await service.list_assistants(account_short_code)

@router.put("", response_model=Assistant)
async def update_assistant(
    assistant: Assistant,
    session: AsyncSession = Depends(get_async_session)
):
    service = AssistantService(repository=AssistantRepository(session))
    updated = await service.update_assistant(assistant)
    if not updated:
        raise HTTPException(status_code=404, detail="Assistant not found or update failed")
    return updated

@router.delete("", response_model=bool)
async def deactivate_assistant(
    delete_request: AssistantDeletion,
    session: AsyncSession = Depends(get_async_session)
):
    service = AssistantService(repository=AssistantRepository(session))
    success = await service.deactivate_assistant(delete_request.id)
    if not success:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return JSONResponse(status_code=200, content={"detail": "Assistant deactivated successfully"})

@router.patch("", response_model=bool)
async def reactivate_assistant(
    delete_request: AssistantDeletion,
    session: AsyncSession = Depends(get_async_session)
):
    service = AssistantService(repository=AssistantRepository(session))
    success = await service.reactivate_assistant(delete_request.id)
    if not success:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return JSONResponse(status_code=200, content={"detail": "Assistant reactivated successfully"})
