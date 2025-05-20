from fastapi import Request
from fastapi.responses import JSONResponse
from backend.util.log_setup import SetupLogging

logger = SetupLogging()

class AccountAlreadyExistsError(Exception):
    """Raised when an account with the given short_code or email already exists."""
    pass

class DatabaseError(Exception):
    """General exception for database errors."""
    pass

class AccountNotFoundError(Exception):
    """Raised when an account is not found."""
    pass


async def account_not_found_exception_handler(request: Request, exc: AccountNotFoundError):
    logger.error(f"Account not found: {exc}")
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)}
    )

async def account_already_exists_exception_handler(request: Request, exc: AccountAlreadyExistsError):
    logger.error(f"Account already exists: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )

async def database_error_exception_handler(request: Request, exc: DatabaseError):
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )

async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )
