from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_role
from app.core.security import get_password_hash
from app.db.supabase_client import get_supabase_client
from app.models.domain import Pump, PumpCreate, Shift, ShiftCreate
from app.models.user import UserCreate, UserInDB, UserPublic, UserRole
from app.telemetries.logger import logger


router = APIRouter(prefix="/owner", tags=["pump-owner"])


@router.get("/pumps", response_model=list[Pump])
def list_pumps(current_user: UserInDB = Depends(require_role(UserRole.PUMP_OWNER))):
    supabase = get_supabase_client()
    resp = (
        supabase.table("pumps")
        .select("*")
        .eq("organisation_id", current_user.organisation_id)
        .order("created_at")
        .execute()
    )
    return resp.data or []


@router.post("/pumps", response_model=Pump, status_code=status.HTTP_201_CREATED)
def create_pump(
    payload: PumpCreate,
    current_user: UserInDB = Depends(require_role(UserRole.PUMP_OWNER)),
):
    if payload.organisation_id != current_user.organisation_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create pump for another organisation")
    supabase = get_supabase_client()
    resp = supabase.table("pumps").insert(payload.model_dump()).execute()
    if not resp.data or len(resp.data) == 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Insert failed")
    created = resp.data[0]
    logger.info("owner", message="Created pump", pump_id=created.get("id"))
    return created


@router.post("/branch-managers", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_branch_manager(
    payload: UserCreate,
    current_user: UserInDB = Depends(require_role(UserRole.PUMP_OWNER)),
):
    if payload.role != UserRole.BRANCH_MANAGER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Branch manager must have role branch_manager",
        )
    if payload.organisation_id != current_user.organisation_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Branch manager must belong to the same organisation",
        )
    supabase = get_supabase_client()
    existing = supabase.table("users").select("id").eq("email", payload.email).maybe_single().execute()
    if existing.data:
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
    logger.info(
        "owner",
        message="Created branch manager",
        user_id=user.id,
        email=user.email,
        organisation_id=user.organisation_id,
    )
    return UserPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        organisation_id=user.organisation_id,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("/shifts", response_model=list[Shift])
def list_shifts(current_user: UserInDB = Depends(require_role(UserRole.PUMP_OWNER))):
    supabase = get_supabase_client()
    resp = (
        supabase.table("shifts")
        .select("*, pumps!inner(organisation_id)")
        .eq("pumps.organisation_id", current_user.organisation_id)
        .order("start_time")
        .execute()
    )
    return resp.data or []


@router.post("/shifts", response_model=Shift, status_code=status.HTTP_201_CREATED)
def create_shift(
    payload: ShiftCreate,
    current_user: UserInDB = Depends(require_role(UserRole.PUMP_OWNER)),
):
    supabase = get_supabase_client()
    # Ensure pump belongs to current owner organisation
    pump_resp = (
        supabase.table("pumps")
        .select("*")
        .eq("id", payload.pump_id)
        .single()
        .execute()
    )
    pump = pump_resp.data
    if not pump or pump.get("organisation_id") != current_user.organisation_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create shift for this pump")

    if payload.manager_id:
        manager_resp = (
            supabase.table("users")
            .select("*")
            .eq("id", payload.manager_id)
            .single()
            .execute()
        )
        manager = manager_resp.data
        if not manager or manager.get("organisation_id") != current_user.organisation_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Manager does not belong to your organisation",
            )

    resp = supabase.table("shifts").insert(payload.model_dump()).execute()
    if not resp.data or len(resp.data) == 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Insert failed")
    created = resp.data[0]
    logger.info("owner", message="Created shift", shift_id=created.get("id"))
    return created

