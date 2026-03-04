from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

from app.api.deps import require_role
from app.db.supabase_client import get_supabase_client
from app.models.domain import Organisation, OrganisationCreate, OrganisationUpdate, Pump
from app.models.user import UserCreate, UserInDB, UserPublic, UserRole
from app.models.notification import ForgotPasswordRequest
from app.core.security import get_password_hash
from app.telemetries.logger import logger


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/organisations", response_model=list[Organisation])
def list_organisations(_: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER))):
    supabase = get_supabase_client()
    resp = supabase.table("organisations").select("*").order("created_at").execute()
    return resp.data or []


@router.post("/organisations", response_model=Organisation, status_code=status.HTTP_201_CREATED)
def create_organisation(
    payload: OrganisationCreate,
    _: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER)),
):
    supabase = get_supabase_client()
    resp = supabase.table("organisations").insert(payload.model_dump()).execute()
    if not resp.data or len(resp.data) == 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Insert failed")
    created = resp.data[0]
    logger.info("admin", message="Created organisation", organisation_id=created.get("id"))
    return created


@router.post("/pump-owners", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_pump_owner(
    payload: UserCreate,
    _: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER)),
):
    if payload.role != UserRole.PUMP_OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pump owner must have role pump_owner",
        )
    supabase = get_supabase_client()
    existing = supabase.table("users").select("id").eq("email", payload.email).maybe_single().execute()
    if getattr(existing, "data", None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    data = payload.model_dump()
    password_hash = get_password_hash(data.pop("password"))
    data["password_hash"] = password_hash
    data["is_active"] = True
    data["failed_login_attempts"] = 0
    data["lock_until"] = None

    resp = supabase.table("users").insert(data).execute()
    if not resp.data or len(resp.data) == 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Insert failed")
    user = UserInDB(**resp.data[0])
    logger.info("admin", message="Created pump owner", user_id=user.id, email=user.email)
    return UserPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        organisation_id=user.organisation_id,
        is_active=user.is_active,
        created_at=user.created_at,
    )


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    organisation_id: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/pump-owners", response_model=list[UserPublic])
def list_pump_owners(_: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER))):
    supabase = get_supabase_client()
    resp = (
        supabase.table("users")
        .select("id, email, full_name, role, organisation_id, is_active, created_at")
        .eq("role", UserRole.PUMP_OWNER.value)
        .order("created_at")
        .execute()
    )
    return [UserPublic(**u) for u in (resp.data or [])]


@router.put("/pump-owners/{user_id}", response_model=UserPublic)
def update_pump_owner(
    user_id: str,
    payload: UserUpdate,
    _: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER)),
):
    supabase = get_supabase_client()
    existing = supabase.table("users").select("*").eq("id", user_id).eq("role", UserRole.PUMP_OWNER.value).single().execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pump owner not found")
    data = payload.model_dump(exclude_unset=True)
    if not data:
        u = existing.data
        return UserPublic(id=u["id"], email=u["email"], full_name=u["full_name"], role=u["role"], organisation_id=u["organisation_id"], is_active=u["is_active"], created_at=u["created_at"])
    resp = supabase.table("users").update(data).eq("id", user_id).select("*").single().execute()
    u = resp.data
    return UserPublic(id=u["id"], email=u["email"], full_name=u["full_name"], role=u["role"], organisation_id=u["organisation_id"], is_active=u["is_active"], created_at=u["created_at"])


@router.delete("/pump-owners/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pump_owner(
    user_id: str,
    _: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER)),
):
    supabase = get_supabase_client()
    supabase.table("users").update({"is_active": False}).eq("id", user_id).eq("role", UserRole.PUMP_OWNER.value).execute()
    return None


@router.get("/branch-managers", response_model=list[UserPublic])
def list_branch_managers(_: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER))):
    supabase = get_supabase_client()
    resp = (
        supabase.table("users")
        .select("id, email, full_name, role, organisation_id, is_active, created_at")
        .eq("role", UserRole.BRANCH_MANAGER.value)
        .order("created_at")
        .execute()
    )
    return [UserPublic(**u) for u in (resp.data or [])]


@router.post("/branch-managers", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_branch_manager(
    payload: UserCreate,
    _: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER)),
):
    if payload.role != UserRole.BRANCH_MANAGER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Branch manager must have role branch_manager",
        )
    supabase = get_supabase_client()
    existing = supabase.table("users").select("id").eq("email", payload.email).maybe_single().execute()
    if getattr(existing, "data", None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )
    data = payload.model_dump()
    password_hash = get_password_hash(data.pop("password"))
    data["password_hash"] = password_hash
    data["is_active"] = True
    data["failed_login_attempts"] = 0
    data["lock_until"] = None
    resp = supabase.table("users").insert(data).execute()
    if not resp.data or len(resp.data) == 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Insert failed")
    user = UserInDB(**resp.data[0])
    logger.info("admin", message="Created branch manager", user_id=user.id, email=user.email)
    return UserPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        organisation_id=user.organisation_id,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.put("/branch-managers/{user_id}", response_model=UserPublic)
def update_branch_manager(
    user_id: str,
    payload: UserUpdate,
    _: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER)),
):
    supabase = get_supabase_client()
    existing = supabase.table("users").select("*").eq("id", user_id).eq("role", UserRole.BRANCH_MANAGER.value).single().execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch manager not found")
    data = payload.model_dump(exclude_unset=True)
    if not data:
        u = existing.data
        return UserPublic(id=u["id"], email=u["email"], full_name=u["full_name"], role=u["role"], organisation_id=u["organisation_id"], is_active=u["is_active"], created_at=u["created_at"])
    resp = supabase.table("users").update(data).eq("id", user_id).select("*").single().execute()
    u = resp.data
    return UserPublic(id=u["id"], email=u["email"], full_name=u["full_name"], role=u["role"], organisation_id=u["organisation_id"], is_active=u["is_active"], created_at=u["created_at"])


@router.delete("/branch-managers/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch_manager(
    user_id: str,
    _: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER)),
):
    supabase = get_supabase_client()
    supabase.table("users").update({"is_active": False}).eq("id", user_id).eq("role", UserRole.BRANCH_MANAGER.value).execute()
    return None


@router.get("/organisations/{org_id}", response_model=Organisation)
def get_organisation(
    org_id: str,
    _: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER)),
):
    supabase = get_supabase_client()
    resp = supabase.table("organisations").select("*").eq("id", org_id).single().execute()
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    return resp.data


@router.get("/organisations/{org_id}/pumps", response_model=list[Pump])
def list_organisation_pumps(
    org_id: str,
    _: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER)),
):
    supabase = get_supabase_client()
    resp = supabase.table("pumps").select("*").eq("organisation_id", org_id).order("created_at").execute()
    return resp.data or []


@router.put("/organisations/{org_id}", response_model=Organisation)
def update_organisation(
    org_id: str,
    payload: OrganisationUpdate,
    _: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER)),
):
    supabase = get_supabase_client()
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    resp = (
        supabase.table("organisations")
        .update(data)
        .eq("id", org_id)
        .select("*")
        .single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    return resp.data


@router.delete("/organisations/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organisation(
    org_id: str,
    _: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER)),
):
    supabase = get_supabase_client()
    supabase.table("organisations").delete().eq("id", org_id).execute()
    return None


class NotificationUpdate(BaseModel):
    status: str = "resolved"


@router.get("/notifications", response_model=list[ForgotPasswordRequest])
def list_notifications(_: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER))):
    supabase = get_supabase_client()
    try:
        resp = supabase.table("forgot_password_requests").select("*").order("created_at", desc=True).execute()
        return [ForgotPasswordRequest(**r) for r in (resp.data or [])]
    except Exception:
        return []


@router.patch("/notifications/{notification_id}")
def update_notification(
    notification_id: str,
    payload: NotificationUpdate,
    _: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER)),
):
    supabase = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    data = {"status": payload.status}
    if payload.status == "resolved":
        data["resolved_at"] = now
    supabase.table("forgot_password_requests").update(data).eq("id", notification_id).execute()
    return {"ok": True}


class AdminStats(BaseModel):
    assets_count: int
    cash_managed_count: int
    organisations_count: int
    managers_count: int


@router.get("/stats", response_model=AdminStats)
def get_stats(_: UserInDB = Depends(require_role(UserRole.SOFTWARE_OWNER))):
    supabase = get_supabase_client()
    pumps = supabase.table("pumps").select("id").execute()
    orgs = supabase.table("organisations").select("id").execute()
    managers = supabase.table("users").select("id").eq("role", UserRole.BRANCH_MANAGER.value).execute()
    return AdminStats(
        assets_count=len(pumps.data or []),
        cash_managed_count=0,
        organisations_count=len(orgs.data or []),
        managers_count=len(managers.data or []),
    )

