from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.supabase_client import get_supabase_client
from app.models.user import Token, UserCreate, UserInDB, UserPublic, UserRole
from app.models.notification import ForgotPasswordCreate
from app.telemetries.logger import logger


router = APIRouter(prefix="/auth", tags=["auth"])


MAX_LOGIN_ATTEMPTS = 3
LOCK_WINDOW_HOURS = 24


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.get("/me", response_model=UserPublic)
def me(current_user: UserInDB = Depends(get_current_user)):
    """Return current authenticated user and role for frontend."""
    return UserPublic(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        organisation_id=current_user.organisation_id,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@router.post("/login", response_model=Token)
def login(payload: LoginRequest):
    """
    Login for all roles.
    Account lock (3 retries per 24 hours) only applies to the software_owner admin.
    """
    supabase = get_supabase_client()
    now = datetime.now(timezone.utc)

    # maybe_single() avoids raising when 0 rows are returned and lets us handle that cleanly
    resp = (
        supabase.table("users")
        .select("*")
        .eq("email", payload.email)
        .maybe_single()
        .execute()
    )
    if not resp.data:
        logger.warning("auth", message="Login failed: user not found", email=payload.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = UserInDB(**resp.data)
    is_admin = user.role == UserRole.SOFTWARE_OWNER

    # Handle lock window (only for admin)
    if is_admin and user.lock_until and now < user.lock_until.replace(tzinfo=timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account locked due to too many failed attempts. Try again later.",
        )

    if not verify_password(payload.password, user.password_hash):
        if is_admin:
            failed_attempts = user.failed_login_attempts + 1
            lock_until = user.lock_until
            if failed_attempts >= MAX_LOGIN_ATTEMPTS:
                lock_until = now + timedelta(hours=LOCK_WINDOW_HOURS)

            supabase.table("users").update(
                {
                    "failed_login_attempts": failed_attempts,
                    "lock_until": lock_until.isoformat() if lock_until else None,
                }
            ).eq("id", user.id).execute()

            logger.warning(
                "auth",
                message="Admin login failed: wrong password",
                email=payload.email,
                failed_attempts=failed_attempts,
            )
        else:
            logger.warning(
                "auth",
                message="Login failed: wrong password",
                email=payload.email,
                role=user.role,
            )

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Successful login, reset counters (only for admin)
    update_payload: dict = {"last_login_at": now.isoformat()}
    if is_admin:
        update_payload["failed_login_attempts"] = 0
        update_payload["lock_until"] = None

    supabase.table("users").update(update_payload).eq("id", user.id).execute()

    access_token = create_access_token({"sub": user.id, "role": user.role, "organisation_id": user.organisation_id})
    logger.info("auth", message="User logged in", email=payload.email, role=user.role)
    return Token(access_token=access_token)


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordCreate):
    """
    Submit a forgot-password request. If the email/phone belongs to a user,
    the request is stored and visible to admin (and pump owner if branch_manager).
    Always returns 200 to avoid leaking existence of accounts.
    """
    supabase = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    user_id = None
    user_role = None
    organisation_id = None

    # Try to find user by email (we don't have phone on user model; treat as email)
    email_or_phone = payload.email_or_phone.strip()
    if "@" in email_or_phone:
        resp = (
            supabase.table("users")
            .select("id, role, organisation_id")
            .eq("email", email_or_phone)
            .maybe_single()
            .execute()
        )
        if resp.data:
            user_id = resp.data["id"]
            user_role = resp.data["role"]
            organisation_id = resp.data.get("organisation_id")

    insert_data = {
        "email_or_phone": email_or_phone,
        "user_id": user_id,
        "user_role": user_role,
        "organisation_id": organisation_id,
        "status": "pending",
        "created_at": now,
    }
    try:
        supabase.table("forgot_password_requests").insert(insert_data).execute()
    except Exception as e:
        logger.warning("auth", message="forgot_password_requests insert failed", error=str(e))
    return {"message": "If an account exists, you will receive instructions."}


@router.post("/bootstrap-admin", response_model=UserPublic)
def bootstrap_admin():
    """
    Idempotent endpoint to ensure the software_owner admin exists.
    Uses credentials from settings (admin@vamisurat.com / vami@surat by default).
    """
    settings = get_settings()
    supabase = get_supabase_client()

    existing = (
        supabase.table("users")
        .select("*")
        .eq("email", settings.software_owner_email)
        .single()
        .execute()
    )

    now = datetime.now(timezone.utc).isoformat()

    if existing.data:
        user = UserInDB(**existing.data)
        return UserPublic(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            organisation_id=user.organisation_id,
            is_active=user.is_active,
            created_at=user.created_at,
        )

    password_hash = get_password_hash(settings.software_owner_password)
    resp = (
        supabase.table("users")
        .insert(
            {
                "email": settings.software_owner_email,
                "full_name": "Software Owner",
                "role": UserRole.SOFTWARE_OWNER.value,
                "password_hash": password_hash,
                "is_active": True,
                "failed_login_attempts": 0,
                "lock_until": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        .select("*")
        .single()
        .execute()
    )

    logger.info(
        "auth",
        message="Bootstrapped software_owner admin user",
        email=settings.software_owner_email,
    )
    created = UserInDB(**resp.data)
    return UserPublic(
        id=created.id,
        email=created.email,
        full_name=created.full_name,
        role=created.role,
        organisation_id=created.organisation_id,
        is_active=created.is_active,
        created_at=created.created_at,
    )

