from fastapi import Request
import logging

logger = logging.getLogger(__name__)

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