"""Authentication middleware for FastAPI.

FR-026: READ public + WRITE authenticated model
- GET requests: Public (no auth required)
- POST/PUT/DELETE requests: Require Bearer token from .env
"""

import os
import logging
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

security = HTTPBearer()


def check_admin_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> bool:
    """Verify admin token from Authorization header.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        True if valid

    Raises:
        HTTPException: 401 if invalid or missing
    """
    # Load admin token from environment
    admin_token = os.getenv("TRADINGAGENTS_ADMIN_TOKEN")

    if not admin_token:
        logger.error("TRADINGAGENTS_ADMIN_TOKEN not configured in .env")
        raise HTTPException(
            status_code=500,
            detail="Server authentication not configured"
        )

    # Verify token
    if credentials.credentials != admin_token:
        logger.warning(f"Invalid token attempt: {credentials.credentials[:10]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing token"
        )

    return True
