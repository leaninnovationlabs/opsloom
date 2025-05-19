from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse

from backend.api.chat.models import ChatRequest, FeedbackRequest, MessageList
from backend.api.chat.services import ChatService
from backend.util.auth_utils import validate_user, TokenData
import logging
from backend.util.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("")
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(validate_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Endpoint to handle an incoming chat message (user -> AI).
    Returns a streaming response from the LLM.
    """
    try:
        chat_service = ChatService(db=db, current_user=current_user)  # pass the DB session
        response_stream = await chat_service.process_chat_request(
            request=request,
            current_user=current_user,
            background_tasks=background_tasks
        )
        return StreamingResponse(response_stream, media_type="application/json")
    except HTTPException as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise e
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/messages", response_model=MessageList)
async def get_messages(
    session_id: str = Query(..., description="The session ID"),
    current_user: TokenData = Depends(validate_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Returns the stored conversation messages for a given session_id.
    """
    try:
        chat_service = ChatService(db=db)
        messages = await chat_service.get_messages(session_id, current_user)
        return messages
    except HTTPException as e:
        logger.error(f"Error in get_messages endpoint: {str(e)}", exc_info=True)
        raise e
    except Exception as e:
        logger.error(f"Error in get_messages endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/feedback")
async def submit_feedback(
    feedback_request: FeedbackRequest,
    current_user: TokenData = Depends(validate_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Update the 'feedback' field for a previously-stored message.
    """
    try:
        chat_service = ChatService(db=db)
        result = await chat_service.submit_feedback(feedback_request, current_user)
        if result:
            return {"status": "success", "message": "Feedback submitted successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to submit feedback")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in submit_feedback endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
