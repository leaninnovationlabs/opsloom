import time
from typing import Dict, Optional
from datetime import datetime
from backend.util.log_setup import SetupLogging

logger = SetupLogging()

class InMemoryTokenBlacklist:
    """
    Simple in-memory token blacklist implementation.
    For production, consider using Redis or another distributed solution.
    """
    def __init__(self):
        # Storage format: {token_identifier: expiry_timestamp}
        self._blacklist: Dict[str, float] = {}
        
    def add_to_blacklist(self, token_id: str, expires_at: float):
        """
        Add a token to the blacklist with its expiration time
        """
        self._blacklist[token_id] = expires_at
        logger.debug(f"Token {token_id[:8]}... added to blacklist")
        
        # Clean expired entries opportunistically (every 10 additions)
        if len(self._blacklist) % 10 == 0:
            self._clean_expired()
    
    def is_blacklisted(self, token_id: str) -> bool:
        """
        Check if a token is in the blacklist
        """
        if token_id not in self._blacklist:
            return False
            
        # If token is in blacklist but expired, remove it
        if self._blacklist[token_id] < time.time():
            del self._blacklist[token_id]
            return False
            
        return True
        
    def _clean_expired(self):
        """
        Remove expired tokens from the blacklist
        """
        current_time = time.time()
        expired_tokens = [
            token_id for token_id, expires_at in self._blacklist.items() 
            if expires_at < current_time
        ]
        
        for token_id in expired_tokens:
            del self._blacklist[token_id]
            
        if expired_tokens:
            logger.debug(f"Removed {len(expired_tokens)} expired tokens from blacklist")

# Singleton instance
token_blacklist = InMemoryTokenBlacklist()

# For use with token validation
def check_token_blacklist(token_id: str) -> bool:
    """
    Check if a token is blacklisted
    """
    return token_blacklist.is_blacklisted(token_id)

def add_token_to_blacklist(token_id: str, expires_at: Optional[datetime] = None):
    """
    Add a token to the blacklist
    """
    # Convert datetime to timestamp or use 1 hour from now
    if expires_at:
        expiry = expires_at.timestamp()
    else:
        expiry = time.time() + 3600  # 1 hour default
        
    token_blacklist.add_to_blacklist(token_id, expiry)