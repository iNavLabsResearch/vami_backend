from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ForgotPasswordRequest(BaseModel):
    id: str
    email_or_phone: str
    user_id: Optional[str] = None
    user_role: Optional[str] = None
    organisation_id: Optional[str] = None
    status: str = "pending"
    created_at: datetime
    resolved_at: Optional[datetime] = None


class ForgotPasswordCreate(BaseModel):
    email_or_phone: str
