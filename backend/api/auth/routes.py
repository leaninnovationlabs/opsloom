from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from backend.util.database import get_async_session

import logging
from backend.util.auth_utils import validate_user, TokenData, create_access_token
from backend.util.domain_utils import extract_subdomain
from backend.util.token_blacklist import add_token_to_blacklist
from backend.api.auth.models import UserCreate, UserLogin, LoggedInUser
from backend.api.auth.responses import create_response, logout_response
from backend.api.auth.repository import UserRepository
from backend.api.account.repository import AccountRepository
from backend.api.account.services import AccountService

from .session import UserManager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/validate")
async def validate(
    current_user: Optional[TokenData] = Depends(validate_user)
):
    """
    Validate a token without DB lookup - just checks JWT validity
    """
    if current_user:
        # Use the data directly from the token
        return JSONResponse(content={
            "auth": "true",
            "message": "Token valid",
            "user": {
                "email": current_user.email,
                "account_id": current_user.account_id,
                "account_short_code": current_user.account_short_code,
                "user_id": current_user.user_id,
            }
        })
    else:
        return JSONResponse(
            status_code=401, 
            content={"detail": "Invalid or expired token"}
        )

@router.post("/login")
async def login(
    request: Request,
    user_login: UserLogin,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Login a user and return a JWT token
    """
    # Extract subdomain for account context
    user_login.account_short_code = extract_subdomain(request)
    
    # Create repositories and services
    user_repository = UserRepository(db)
    account_repository = AccountRepository(db)
    account_service = AccountService(account_repository)
    
    # Create user manager
    user_manager = UserManager(
        user_repository=user_repository, 
        account_service=account_service
    )

    # Attempt login
    access_token, message, loggedin_user = await user_manager.login_user(user_login)
    
    if access_token:
        return create_response(access_token, loggedin_user, message)
    else:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid credentials"}
        )

@router.post("/logout")
async def logout(current_user: Optional[TokenData] = Depends(validate_user)):
    """
    Logout user by clearing their token and adding it to blacklist
    """
    # If we have a valid user from the token
    if current_user and current_user.exp:
        # Create a unique token identifier
        token_id = f"{current_user.user_id}:{current_user.exp.timestamp() if current_user.exp else 0}"
        
        # Add the token to the blacklist
        add_token_to_blacklist(token_id, current_user.exp)
        
        logger.info(f"Logged out and blacklisted token for user: {current_user.email}")
        return logout_response()
    
    # If no user logged in, still return success
    return JSONResponse(
        content={"auth": "false", "message": "Not logged in"}
    )

@router.post("/signup")
async def signup(
    request: Request,
    user_create: UserCreate,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Create a new user account
    """
    try:
        # Handle multitenant setup
        from backend.util.config import get_config_value
        if get_config_value("multitenant") == "true":
            subdomain = extract_subdomain(request)
            user_create.account_shortcode = subdomain
        else:
            user_create.account_shortcode = "default"

        # Create repositories and services
        user_repository = UserRepository(db)
        account_repository = AccountRepository(db)
        account_service = AccountService(account_repository)

        # Create user manager
        user_manager = UserManager(
            user_repository=user_repository,
            account_service=account_service
        )

        # Attempt signup
        access_token, message, loggedin_user = await user_manager.signup_user(user_create)
        
        if access_token:
            return create_response(access_token, loggedin_user, message)
        else:
            return JSONResponse(
                status_code=400, 
                content={"detail": message or "Invalid signup data"}
            )

    except Exception as e:
        logger.error(f"Signup error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error during signup: {str(e)}"}
        )

@router.get("/refresh")
async def refresh_token(current_user: TokenData = Depends(validate_user)):
    """
    Refresh a valid token to extend its expiration
    No DB lookup needed - just create a new token
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Create a new token with fresh expiration time
    new_token = create_access_token(current_user)
    
    # Create a logged in user object from token data
    user = LoggedInUser(
        email=current_user.email,
        account_id=current_user.account_id, 
        account_short_code=current_user.account_short_code,
        user_id=current_user.user_id
    )
    
    return create_response(
        access_token=new_token,
        user=user,
        message="Token refreshed"
    )