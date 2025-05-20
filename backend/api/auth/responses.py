import json
from fastapi import Response
from backend.api.auth.models import LoggedInUser, User
from backend.util.config import get_config_value
from backend.util.log_setup import SetupLogging
import os

logger = SetupLogging()

def get_cookie_domain():
    """Helper to determine cookie domain based on config"""
    is_multitenant = get_config_value("multitenant").lower() == "true"
    base_domain = get_config_value("base_domain")
    
    if not base_domain:
        base_domain = "localhost"
    else:
        base_domain = base_domain.strip()
        
    return base_domain

def create_response(
    access_token: str,
    user: LoggedInUser,
    message: str
):
    """
    Create a response with the access_token cookie and user data
    """
    # Include user data in response
    content = json.dumps({
        "auth": "true",
        "message": message,
        "user": user.model_dump()
    })
    
    response = Response(content=content, media_type="application/json")
    
    # Get domain settings
    base_domain = get_cookie_domain()
    is_multitenant = get_config_value("multitenant").lower() == "true"
    
    # Determine domain for cookie
    if is_multitenant:
        domain = f"{user.account_short_code}.{base_domain}"
    else:
        domain = base_domain
    
    # Get cookie security settings
    is_https = get_config_value("HTTPS") == "true"
    
    # Get token expiry time from env or config (default 1 hour)
    max_age = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", "3600"))
    
    logger.debug(f"Setting cookie on domain: {domain}")
    
    # Set the cookie with appropriate security settings
    response.set_cookie(
        key="access-token",
        value=access_token,
        # domain=domain,  # Commented out for local testing, uncomment in production
        max_age=max_age,
        httponly=True,  # Always set HttpOnly for security
        # secure=is_https,  # Set secure flag based on HTTPS config
        samesite="lax",
        path="/"
    )
    
    return response


def logout_response(user: User = None):
    """
    Create a response that clears the access token cookie
    """
    response = Response(
        content=json.dumps({"auth": "false", "message": "Logged out"}),
        media_type="application/json"
    )
    
    # Get domain settings
    base_domain = get_cookie_domain()
    is_multitenant = get_config_value("multitenant").lower() == "true"
    
    # Determine domain for cookie deletion
    domain = base_domain
    if user and is_multitenant:
        domain = f"{user.account_short_code}.{base_domain}"
    
    # Get cookie security settings
    is_https = get_config_value("HTTPS") == "true"
    
    logger.debug(f"Clearing cookie on domain: {domain}")
    
    # Clear the access token cookie
    response.delete_cookie(
        key="access-token",
        # domain=domain,  # Commented out for local testing, uncomment in production
        path="/",
        httponly=True,
        secure=is_https,
        samesite="lax"
    )
    
    # Clear any other session cookies
    response.delete_cookie(
        key="session-id",
        # domain=domain,  # Commented out for local testing, uncomment in production
        path="/",
        httponly=True,
        secure=is_https,
        samesite="lax"
    )
    
    return response