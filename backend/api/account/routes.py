from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.account.models import AccountConfigResponse, AccountCreate, AccountUpdate, AccountResponse
from backend.api.account.services import AccountService
from backend.api.account.repository import AccountRepository
from backend.lib.exceptions import (
    AccountAlreadyExistsError,
    DatabaseError,
    AccountNotFoundError
)
from backend.util.auth_utils import validate_user, TokenData
from backend.util.log_setup import SetupLogging
from backend.util.database import get_async_session

logger = SetupLogging()
router = APIRouter()

@router.post("", response_model=AccountResponse)
async def create_account(
    account_create: AccountCreate,
    current_user: TokenData = Depends(validate_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Create a new account row in the database.
    """
    account_service = AccountService(repository=AccountRepository(db))
    try:
        account = await account_service.create_account(account_create)
        return AccountResponse(account=account)
    except AccountAlreadyExistsError as e:
        logger.error(f"Account creation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except DatabaseError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    except Exception as e:
        logger.error(f"Unexpected error in create_account endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/config/{short_code}", response_model=AccountConfigResponse, response_model_by_alias=False)
async def get_account_config(
    short_code: str,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Fetch only the config (metadata + protection) for an account, by short_code.
    """
    account_service = AccountService(repository=AccountRepository(db))
    try:
        account_conf = await account_service.get_account_config_by_short_code(short_code)
        return account_conf
    except AccountNotFoundError as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except DatabaseError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    except Exception as e:
        logger.error(f"Unexpected error in get_account_config endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{account_id}", response_model=AccountResponse, response_model_by_alias=False)
async def get_account(
    account_id: UUID,
    current_user: TokenData = Depends(validate_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Retrieve an account by its UUID.
    """
    account_service = AccountService(repository=AccountRepository(db))
    try:
        account = await account_service.get_account(account_id)
        return AccountResponse(account=account)
    except AccountNotFoundError as e:
        logger.error(f"Account not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except DatabaseError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    except Exception as e:
        logger.error(f"Unexpected error in get_account endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: UUID,
    account_update: AccountUpdate,
    current_user: TokenData = Depends(validate_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Update an account by ID, using the fields in 'account_update'.
    """
    account_service = AccountService(repository=AccountRepository(db))
    try:
        updated = await account_service.update_account(account_id, account_update)
        return AccountResponse(account=updated)
    except AccountNotFoundError as e:
        logger.error(f"Account not found for update: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except DatabaseError as e:
        logger.error(f"Database error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    except Exception as e:
        logger.error(f"Error in update_account endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
