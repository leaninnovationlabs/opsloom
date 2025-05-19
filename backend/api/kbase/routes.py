from fastapi import APIRouter, HTTPException, Depends, Request
from uuid import UUID
from backend.api.kbase.models import KnowledgeBase, KnowledgeBaseList
from backend.api.kbase.services import KbaseService
from backend.api.kbase.repository import KbaseRepository
from backend.util.auth_utils import validate_user, TokenData
import logging
from backend.util.domain_utils import extract_subdomain
from backend.util.database import get_async_session  # your async session dependency
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=KnowledgeBase)
async def create_kbase(
    request: Request,
    kbase: KnowledgeBase,
    current_user: TokenData = Depends(validate_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        kbase.account_short_code = extract_subdomain(request)
        service = KbaseService(repository=KbaseRepository(session))
        result = await service.create_kbase(kbase)
        if result:
            return result
        else:
            raise HTTPException(status_code=400, detail="Failed to create KnowledgeBase")
    except Exception as e:
        logger.error(f"Error in create_kbase endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("", response_model=KnowledgeBaseList)
async def list_kbases(
    current_user: TokenData = Depends(validate_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        service = KbaseService(repository=KbaseRepository(session))
        result = await service.list_kbases()
        return result
    except Exception as e:
        logger.error(f"Error in list_kbases endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{uuid}", response_model=KnowledgeBase)
async def get_kbase(
    uuid: UUID,
    current_user: TokenData = Depends(validate_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        service = KbaseService(repository=KbaseRepository(session))
        result = await service.get_kbase(uuid)
        if not result:
            raise HTTPException(status_code=404, detail="KnowledgeBase not found")
        return result
    except Exception as e:
        logger.error(f"Error in get_kbase endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{uuid}", response_model=KnowledgeBase)
async def update_kbase(
    uuid: UUID,
    kbase: KnowledgeBase,
    current_user: TokenData = Depends(validate_user),
    session: AsyncSession = Depends(get_async_session)
):
    try:
        kbase.id = uuid  # ensure path param is used
        service = KbaseService(repository=KbaseRepository(session))
        result = await service.update_kbase(kbase)
        if not result:
            raise HTTPException(status_code=404, detail="KnowledgeBase not found")
        return result
    except Exception as e:
        logger.error(f"Error in update_kbase endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{uuid}", response_model=dict)
async def delete_kbase(
    uuid: UUID,
    current_user: TokenData = Depends(validate_user),
    session: AsyncSession = Depends(get_async_session)
):
    try:
        service = KbaseService(repository=KbaseRepository(session))
        success = await service.delete_kbase(uuid)
        if success:
            return {"status": "success", "message": "KnowledgeBase deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="KnowledgeBase not found")
    except Exception as e:
        logger.error(f"Error in delete_kbase endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
