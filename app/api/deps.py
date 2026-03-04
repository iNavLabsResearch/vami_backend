from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.db.supabase_client import get_supabase_client
from app.models.user import TokenPayload, UserInDB, UserRole
from app.telemetries.logger import logger


reusable_oauth2 = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(reusable_oauth2)],
) -> UserInDB:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    token_data = TokenPayload(**payload)
    supabase = get_supabase_client()
    resp = (
        supabase.table("users")
        .select("*")
        .eq("id", token_data.sub)
        .single()
        .execute()
    )
    if resp.data is None:
        logger.warning("auth", message="User not found for token", user_id=token_data.sub)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    user = UserInDB(**resp.data)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    # Enforce 3 login attempts per 24 hours at auth time as well, but only for admin
    if (
        user.role == UserRole.SOFTWARE_OWNER
        and user.lock_until
        and datetime.now(timezone.utc) < user.lock_until.replace(tzinfo=timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account locked due to too many failed attempts. Try again later.",
        )

    return user


def require_role(required: UserRole):
    def _role_dependency(user: UserInDB = Depends(get_current_user)) -> UserInDB:
        if user.role != required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _role_dependency


def require_any_role(*roles: UserRole):
    def _role_dependency(user: UserInDB = Depends(get_current_user)) -> UserInDB:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _role_dependency

