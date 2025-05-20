from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from backend.api.session.models import (
    SessionRequest, SessionList, SessionResponse
)
from backend.api.session.services import SessionService
from backend.util.auth_utils import validate_user, TokenData
from backend.util.log_setup import SetupLogging
from backend.util.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
logger = SetupLogging()

@router.post("", response_model=SessionResponse)
async def create_session(
    request: SessionRequest,
    current_user: TokenData = Depends(validate_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Create a new session, referencing the user's account 
    and chosen assistant (if needed).
    """
    try:
        session_service = SessionService(db=db)
        new_session = await session_service.create_session_object(
            curr_user=current_user,
            assistant_id=request.assistant_id
        )
        saved_session = await session_service.store_chat_session(new_session)
        if not saved_session:
            raise HTTPException(status_code=400, detail="Failed to create session")
        return SessionResponse(session=saved_session)
    except Exception as e:
        logger.error(f"Error in create_session endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("", response_model=SessionList)
async def list_sessions(
    current_user: TokenData = Depends(validate_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Return all sessions for the given user.
    """
    try:
        session_service = SessionService(db=db)
        logger.debug(f"Listing sessions for user {current_user.user_id}")
        user_sessions = await session_service.list_sessions(current_user.user_id)
        return user_sessions
    except Exception as e:
        logger.error(f"Error in list_sessions endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{session_id}", response_model=dict)
async def delete_session(
    session_id: UUID,
    current_user: TokenData = Depends(validate_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Delete the specified session by ID.
    """
    try:
        session_service = SessionService(db=db)
        success = await session_service.delete_session(session_id)
        if success:
            return {"status": "success", "message": "Session deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{session_id}/title")
async def update_session_title(
    session_id: UUID,
    title: str,
    current_user: TokenData = Depends(validate_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Update the title of an existing session.
    """
    try:
        session_service = SessionService(db=db)
        success = await session_service.update_session_title(session_id, title)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found or update failed")
        return {"status": "success", "message": "Session title updated"}
    except Exception as e:
        logger.error(f"Error updating session title: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
