from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.index.models import IndexResponse
from backend.util.auth_utils import validate_user, TokenData
from backend.api.index.service import IndexService
from backend.util.database import get_async_session
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=IndexResponse)
async def index_document(
    kbase_name: str = Form(...),
    file: UploadFile = File(...),
    current_user: TokenData = Depends(validate_user),
    session: AsyncSession = Depends(get_async_session),  
):
    try:
        # Pass the injected session to IndexService.
        index_service = IndexService(kbase_name, session)
        s3_uri = await index_service.process_and_index_document(file, kbase_name)
        return IndexResponse(message="Document processed and indexed successfully", s3_uri=s3_uri)
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Unexpected error in index_document endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
