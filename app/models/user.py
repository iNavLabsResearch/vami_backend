from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    SOFTWARE_OWNER = "software_owner"
    PUMP_OWNER = "pump_owner"
    BRANCH_MANAGER = "branch_manager"


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole
    organisation_id: Optional[str] = Field(default=None, description="Org this user belongs to")


class UserCreate(UserBase):
    password: str


class UserInDB(UserBase):
    id: str
    password_hash: str
    is_active: bool = True
    failed_login_attempts: int = 0
    lock_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class UserPublic(UserBase):
    id: str
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    role: UserRole
    organisation_id: Optional[str] = None

