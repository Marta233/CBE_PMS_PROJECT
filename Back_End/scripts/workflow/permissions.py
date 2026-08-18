from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..db.models import (
    ActionType,
    ObjectiveSet,
    OrgUnit,
    RolePermission,
    ScopeType,
    StatusTransition,
    UserRole,
    UserRoleAssignment,
)


@dataclass(frozen=True)
class ActorContext:
    user_id: int
    email: str
    name: str
    roles: list[UserRole]
    assignments: list[UserRoleAssignment]


def _role_allows(db: Session, role: UserRole, action: ActionType) -> bool:
    rp = (
        db.query(RolePermission)
        .filter(RolePermission.role == role, RolePermission.action == action)
        .one_or_none()
    )
    return bool(rp and rp.allowed)


def can_any_role(db: Session, actor: ActorContext, action: ActionType) -> bool:
    return any(_role_allows(db, role, action) for role in actor.roles)


def _ancestors(db: Session, unit_id: int) -> Iterable[int]:
    current = db.query(OrgUnit).filter(OrgUnit.id == unit_id).one_or_none()
    while current and current.parent_id:
        yield current.parent_id
        current = db.query(OrgUnit).filter(OrgUnit.id == current.parent_id).one_or_none()


def _is_within_scope(db: Session, set_unit_id: int, scope_type: ScopeType, scope_id: Optional[int]) -> bool:
    if scope_type == ScopeType.global_scope:
        return True
    if scope_id is None:
        return False
    if scope_type == ScopeType.unit:
        return set_unit_id == scope_id
    if scope_type in (ScopeType.department, ScopeType.division):
        return scope_id in set(_ancestors(db, set_unit_id))
    return False


def assert_scope_for_set(db: Session, actor: ActorContext, objective_set: ObjectiveSet) -> None:
    for a in actor.assignments:
        if _is_within_scope(db, objective_set.unit_id, a.scope_type, a.scope_id):
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: outside your scope.")


def assert_can(db: Session, actor: ActorContext, action: ActionType) -> None:
    if not can_any_role(db, actor, action):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: action not permitted.")


def resolve_transition(
    db: Session,
    actor: ActorContext,
    from_status,
    action: ActionType,
) -> StatusTransition:
    # Find the first role that has a configured transition.
    for role in actor.roles:
        st = (
            db.query(StatusTransition)
            .filter(
                StatusTransition.from_status == from_status,
                StatusTransition.action == action,
                StatusTransition.actor_role == role,
            )
            .one_or_none()
        )
        if st is not None:
            return st
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: invalid transition for your role.")

