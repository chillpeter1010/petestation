from fastapi import HTTPException, Request, status

from app.services.auth_service import UserRecord


def require_user(request: Request) -> UserRecord:
    user = getattr(request.state, "auth_user", None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return user


def require_admin(request: Request) -> UserRecord:
    user = require_user(request)
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required.")
    return user
