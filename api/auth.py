from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status


def get_current_user(request: Request) -> Dict[str, Any]:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")
    return user


def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if not bool(user.get("is_admin", False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


def build_session_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "username": user["username"],
        "is_admin": bool(user.get("is_admin", False)),
        "is_active": bool(user.get("is_active", True)),
    }
