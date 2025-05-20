from fastapi import Depends, HTTPException, Request
from jwt import PyJWTError, ExpiredSignatureError, InvalidTokenError
from fastapi.security import APIKeyCookie, APIKeyHeader
import jwt
from dotenv import load_dotenv
from argon2 import PasswordHasher
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from backend.util.log_setup import SetupLogging
from backend.util.config import get_config_value
from backend.util.domain_utils import extract_subdomain
from backend.util.token_blacklist import check_token_blacklist
import os

logger = SetupLogging()

# Load environment variables
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

cookie_security = APIKeyCookie(name="access-token", auto_error=False)
header_security = APIKeyHeader(name="access-token", auto_error=False)

class TokenData(BaseModel):
    email: Optional[str] = None
    account_id: str 
    account_short_code: str
    user_id: str
    exp: Optional[datetime] = None
    
    class Config:
        arbitrary_types_allowed = True

def create_access_token(data: TokenData) -> str:
    """
    Create a JWT token with expiry time
    """
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    
    to_encode = {
        "email": data.email,
        "account_id": data.account_id,
        "account_short_code": data.account_short_code,
        "user_id": data.user_id,
        "exp": expire.timestamp()  # Add expiration time
    }
    
    encoded_jwt = jwt.encode(
        payload=to_encode,
        key=SECRET_KEY,
        algorithm=ALGORITHM
    )
    return encoded_jwt

async def get_token_from_cookie_or_header(
    token_from_cookie: Optional[str] = Depends(cookie_security),
    token_from_header: Optional[str] = Depends(header_security),
):
    """
    Get token from either cookie or header
    """
    if token_from_cookie:
        return token_from_cookie

    if token_from_header:
        return token_from_header

    logger.debug("No token found in cookie or header.")
    return None

async def validate_user(
    request: Request,
    token: Optional[str] = Depends(get_token_from_cookie_or_header)
) -> Optional[TokenData]:
    """
    Validate user from JWT token without DB lookup
    """
    if not token:
        return None

    try:
        # Decode and validate token
        payload = jwt.decode(
            jwt=token,
            key=SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        
        # Extract user data from token
        email: str = payload.get("email")
        account_id: str = payload.get("account_id")
        account_short_code: str = payload.get("account_short_code")
        user_id: str = payload.get("user_id")
        exp: float = payload.get("exp")
        token_id = f"{user_id}:{exp}"

        # Check if token has been blacklisted (e.g., after logout)
        if check_token_blacklist(token_id):
            logger.error(f"Token is blacklisted")
            raise HTTPException(
                status_code=401,
                detail="Token has been invalidated"
            )
    
        
        # Check if token is expired
        if exp and datetime.now(timezone.utc).timestamp() > exp:
            logger.error("Token has expired")
            raise HTTPException(
                status_code=401,
                detail="Token expired"
            )
            
        if not all([account_id, account_short_code, user_id]):
            logger.error("Missing required fields in token payload")
            return None
            
        token_data = TokenData(
            email=email,
            account_id=account_id,
            account_short_code=str(account_short_code),
            user_id=user_id,
            exp=datetime.fromtimestamp(exp) if exp else None
        )

        if not token_data:
            logger.info(f"invalid or expired token: {payload}")
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        # Check multitenancy if enabled
        is_multitenant = get_config_value("multitenant").lower() == "true"
        
        if is_multitenant:
            request_subdomain = extract_subdomain(request)
            
            # Verify subdomain matches user's account_short_code
            if request_subdomain != "default" and request_subdomain != token_data.account_short_code:
                logger.error(f"Tenant mismatch - Token account_short_code: {token_data.account_short_code}, Request subdomain: {request_subdomain}")
                raise HTTPException(
                    status_code=403,
                    detail="Access denied - tenant mismatch"
                )

        return token_data

    except ExpiredSignatureError:
        logger.error("Token has expired")
        raise HTTPException(
            status_code=401,
            detail="Token expired"
        )
    except InvalidTokenError:
        logger.error("Invalid token format")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )
    except PyJWTError as e:
        logger.error(f"Error decoding token: {e}")
        return None

class PasswordService:
    def __init__(self):
        self.ph = PasswordHasher()
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using Argon2.
        """
        try:
            hashed_password = self.ph.hash(password)
            return hashed_password
        except Exception as e:
            logger.error(f"Error hashing password: {e}")
            raise

    def verify_password(self, stored_password: str, provided_password: str) -> bool:
        """
        Verify a password against its hash using Argon2.
        """
        if not stored_password or not provided_password:
            return False
        
        # Clean both passwords
        clean_stored = stored_password.strip()
        clean_provided = provided_password.strip()
         
        try:
            if clean_stored.startswith('$argon2'):
                try:
                    result = self.ph.verify(clean_stored, clean_provided)
                    return result
                except Exception as e:
                    logger.error(f"Error during Argon2 verification: {e}")
                    return False
            else:
                logger.error("Unable to verify password: stored password is not a valid Argon2 hash.")
                return False
                
        except Exception as e:
            logger.error(f"Error during password verification: {e}")
            return False
            
    def validate_password_requirements(self, password: str) -> tuple[bool, str]:
        """
        Validate password meets minimum requirements.
        Returns (is_valid, error_message)
        """
        if len(password) < 4:
            return False, "Password must be at least 4 characters long"
        return True, ""
