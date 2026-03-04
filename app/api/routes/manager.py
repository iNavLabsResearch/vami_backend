from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.db.supabase_client import get_supabase_client
from app.models.domain import Pump, Shift
from app.models.user import UserInDB, UserRole


router = APIRouter(prefix="/manager", tags=["branch-manager"])


@router.get("/me", response_model=UserInDB)
def get_profile(current_user: UserInDB = Depends(require_role(UserRole.BRANCH_MANAGER))):
    return current_user


@router.get("/pumps", response_model=list[Pump])
def get_my_pumps(current_user: UserInDB = Depends(require_role(UserRole.BRANCH_MANAGER))):
    supabase = get_supabase_client()
    # Pumps belonging to manager's organisation
    resp = (
        supabase.table("pumps")
        .select("*")
        .eq("organisation_id", current_user.organisation_id)
        .order("created_at")
        .execute()
    )
    return resp.data or []


@router.get("/shifts", response_model=list[Shift])
def get_my_shifts(current_user: UserInDB = Depends(require_role(UserRole.BRANCH_MANAGER))):
    supabase = get_supabase_client()
    resp = (
        supabase.table("shifts")
        .select("*")
        .eq("manager_id", current_user.id)
        .order("start_time")
        .execute()
    )
    return resp.data or []

