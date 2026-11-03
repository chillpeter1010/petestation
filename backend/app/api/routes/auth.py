from functools import lru_cache

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from app.api.dependencies.auth import require_admin, require_user
from app.api.schemas.auth import AuthResponse, AuthUser, AvatarUpdateRequest, LoginRequest, RegisterRequest, RegisterResponse, UserListResponse, UserProfileRequest, UserStatusRequest
from app.core.config import settings
from app.services.auth_service import AuthServiceError, AuthStore, UserRecord


SESSION_COOKIE = "petehub_session"
router = APIRouter()


@lru_cache(maxsize=1)
def get_auth_store() -> AuthStore:
    return AuthStore(settings.auth_db_path)


def auth_user(user: UserRecord) -> AuthUser:
    return AuthUser(**user.as_dict())


def auth_error(exc: AuthServiceError) -> HTTPException:
    code = status.HTTP_409_CONFLICT if exc.code == "username_exists" else status.HTTP_400_BAD_REQUEST
    if exc.code in {"invalid_credentials", "pending_approval", "account_disabled"}:
        code = status.HTTP_401_UNAUTHORIZED if exc.code == "invalid_credentials" else status.HTTP_403_FORBIDDEN
    if exc.code == "user_not_found":
        code = status.HTTP_404_NOT_FOUND
    return HTTPException(status_code=code, detail={"code": exc.code, "message": str(exc)})


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> RegisterResponse:
    try:
        user = get_auth_store().create_user(
            payload.username,
            payload.password,
            favorite_team_id=payload.favorite_team_id,
        )
    except AuthServiceError as exc:
        raise auth_error(exc) from exc
    return RegisterResponse(user=auth_user(user), message="Registration received. An administrator must approve this account before sign-in.")


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> AuthResponse:
    try:
        user = get_auth_store().authenticate(payload.username, payload.password)
    except AuthServiceError as exc:
        raise auth_error(exc) from exc
    token, _ = get_auth_store().create_session(user.id, settings.auth_session_days)
    secure_cookie = settings.auth_cookie_secure or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.auth_session_days * 86_400,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return AuthResponse(user=auth_user(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> None:
    get_auth_store().revoke_session(session)
    secure_cookie = settings.auth_cookie_secure or request.headers.get("x-forwarded-proto") == "https"
    response.delete_cookie(SESSION_COOKIE, path="/", secure=secure_cookie, samesite="lax")


@router.get("/me", response_model=AuthResponse)
def me(user: UserRecord = Depends(require_user)) -> AuthResponse:
    return AuthResponse(user=auth_user(user))


@router.patch("/profile", response_model=AuthResponse)
def update_profile(payload: UserProfileRequest, user: UserRecord = Depends(require_user)) -> AuthResponse:
    favorite_team_id = payload.favorite_team_id if "favorite_team_id" in payload.model_fields_set else user.favorite_team_id
    avatar_setup_status = payload.avatar_setup_status or user.avatar_setup_status
    try:
        updated = get_auth_store().update_profile(
            user.id,
            favorite_team_id=favorite_team_id,
            avatar_setup_status=avatar_setup_status,
        )
    except AuthServiceError as exc:
        raise auth_error(exc) from exc
    return AuthResponse(user=auth_user(updated))


@router.patch("/avatar", response_model=AuthResponse)
def update_avatar(payload: AvatarUpdateRequest, user: UserRecord = Depends(require_user)) -> AuthResponse:
    try:
        updated = get_auth_store().update_avatar(user.id, payload.avatar)
    except AuthServiceError as exc:
        raise auth_error(exc) from exc
    return AuthResponse(user=auth_user(updated))


@router.get("/users", response_model=UserListResponse)
def users(_: UserRecord = Depends(require_admin)) -> UserListResponse:
    return UserListResponse(users=[auth_user(user) for user in get_auth_store().list_users()])


@router.patch("/users/{user_id}", response_model=AuthResponse)
def update_user(user_id: int, payload: UserStatusRequest, actor: UserRecord = Depends(require_admin)) -> AuthResponse:
    try:
        user = get_auth_store().set_user_status(user_id, payload.status, actor_user_id=actor.id)
    except AuthServiceError as exc:
        raise auth_error(exc) from exc
    return AuthResponse(user=auth_user(user))
