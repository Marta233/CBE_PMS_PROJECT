from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.init_db import verify_password
from ...db.models import OrgUnit, ScopeType, User, UserRole, UserRoleAssignment
from ...workflow.permissions import ActorContext


JWT_SECRET = os.getenv("PMS_JWT_SECRET", "dev-secret-change-me")
JWT_ISSUER = os.getenv("PMS_JWT_ISSUER", "cbe-pms")
JWT_TTL_MINUTES = int(os.getenv("PMS_JWT_TTL_MINUTES", "480"))


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RoleAssignmentOut(BaseModel):
    role: str
    scope_type: str
    scope_id: int | None


class ManagerScopeOut(BaseModel):
    unit_id: int
    unit_name: str
    department: str
    division: str


class DirectorScopeOut(BaseModel):
    departments: list[str]
    division: str


class MeResponse(BaseModel):
    id: int
    email: str
    name: str
    roles: list[str]
    assignments: list[RoleAssignmentOut]
    manager_scope: ManagerScopeOut | None = None
    director_scope: DirectorScopeOut | None = None


def _resolve_manager_scope(db: Session, assignments: list[UserRoleAssignment]) -> ManagerScopeOut | None:
    for a in assignments:
        if a.role != UserRole.manager or a.scope_type != ScopeType.unit or a.scope_id is None:
            continue
        unit = db.query(OrgUnit).filter(OrgUnit.id == a.scope_id).one_or_none()
        if unit is None:
            continue
        return ManagerScopeOut(
            unit_id=unit.id,
            unit_name=unit.name,
            department=unit.department,
            division=unit.division,
        )
    return None


def _resolve_director_scope(db: Session, assignments: list[UserRoleAssignment]) -> DirectorScopeOut | None:
    departments: list[str] = []
    division = ""
    for a in assignments:
        if a.role != UserRole.unit_director or a.scope_type != ScopeType.department or a.scope_id is None:
            continue
        dept_unit = db.query(OrgUnit).filter(OrgUnit.id == a.scope_id).one_or_none()
        if dept_unit is None:
            continue
        departments.append(dept_unit.name)
        if dept_unit.division:
            division = dept_unit.division
    if not departments:
        return None
    return DirectorScopeOut(departments=sorted(set(departments)), division=division)


def _issue_token(user: User) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "iss": JWT_ISSUER,
        "sub": str(user.id),
        "email": user.email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_TTL_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.email == req.email, User.is_active == True).one_or_none()  # noqa: E712
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    return LoginResponse(access_token=_issue_token(user))


def get_current_actor(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
) -> ActorContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], issuer=JWT_ISSUER)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    user_id = int(payload.get("sub") or 0)
    user = db.query(User).filter(User.id == user_id, User.is_active == True).one_or_none()  # noqa: E712
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    assignments = db.query(UserRoleAssignment).filter(UserRoleAssignment.user_id == user.id).all()
    roles = sorted({a.role for a in assignments}, key=lambda r: r.value)
    return ActorContext(
        user_id=user.id,
        email=user.email,
        name=user.name,
        roles=list(roles),
        assignments=assignments,
    )


@router.get("/me", response_model=MeResponse)
def me(
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> MeResponse:
    return MeResponse(
        id=actor.user_id,
        email=actor.email,
        name=actor.name,
        roles=[r.value for r in actor.roles],
        assignments=[
            RoleAssignmentOut(role=a.role.value, scope_type=a.scope_type.value, scope_id=a.scope_id)
            for a in actor.assignments
        ],
        manager_scope=_resolve_manager_scope(db, actor.assignments),
        director_scope=_resolve_director_scope(db, actor.assignments),
    )

