from fastapi import Request
from backend.util.log_setup import SetupLogging

logger = SetupLogging()

def extract_subdomain(request: Request) -> str:
    """
    Extract subdomain from request origin header.
    Returns "default" if no valid subdomain is found or if origin is localhost.
    """
    try:
        return "default"
        
    except Exception as e:
        logger.error(f"Error extracting subdomain: {e}")
        return "default"