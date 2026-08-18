from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import ObjectiveSet, ObjectiveSetStatus, PositionObjectiveStatus, User, UserRole
from .auth import get_current_actor
from ...workflow.permissions import ActorContext, assert_scope_for_set
from ...workflow.position_status import list_position_statuses


router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: str
    set_id: int
    title: str
    message: str
    unit_name: str
    department: str
    division: str
    status: str
    actor_name: str
    timestamp: str
    position_count: int = 0


class NotificationsResponse(BaseModel):
    unread_count: int
    notifications: list[NotificationOut]


def _manager_name(db: Session, manager_id: int) -> str:
    u = db.query(User).filter(User.id == manager_id).one_or_none()
    if u is None:
        return "A manager"
    return u.name or u.email


def _statuses_for_role(role: UserRole) -> set[ObjectiveSetStatus]:
    if role == UserRole.unit_director:
        return {ObjectiveSetStatus.activated_to_director, ObjectiveSetStatus.vp_rejected_to_director}
    if role == UserRole.vp:
        return {ObjectiveSetStatus.director_approved_and_activated_to_vp}
    if role == UserRole.manager:
        return {ObjectiveSetStatus.director_rejected_to_manager}
    if role == UserRole.pms:
        return {ObjectiveSetStatus.sent_to_pms}
    return set()


def _matching_positions(db: Session, set_id: int, wanted: set[ObjectiveSetStatus]) -> list[PositionObjectiveStatus]:
    return [row for row in list_position_statuses(db, set_id) if row.status in wanted]


def _notification_for_set(
    db: Session,
    actor: ActorContext,
    s: ObjectiveSet,
    matching: list[PositionObjectiveStatus],
) -> NotificationOut | None:
    if not matching:
        return None

    unit = s.unit
    manager = _manager_name(db, s.manager_id)
    unit_label = unit.name if unit else "unit"
    count = len(matching)
    # Prefer the most common matching status for the notification copy.
    status = matching[0].status
    pos_label = f"{count} position{'s' if count != 1 else ''}"

    if status == ObjectiveSetStatus.activated_to_director and UserRole.unit_director in actor.roles:
        return NotificationOut(
            id=f"set-{s.id}-director",
            set_id=s.id,
            title="Approval required",
            message=f"{manager} submitted {pos_label} for {unit_label}. Waiting for your approval.",
            unit_name=unit_label,
            department=unit.department if unit else "",
            division=unit.division if unit else "",
            status=status.value,
            actor_name=manager,
            timestamp=s.updated_at.isoformat(),
            position_count=count,
        )

    if status == ObjectiveSetStatus.vp_rejected_to_director and UserRole.unit_director in actor.roles:
        return NotificationOut(
            id=f"set-{s.id}-vp-reject",
            set_id=s.id,
            title="VP returned for revision",
            message=f"VP sent back {pos_label} for {unit_label}. Please review and resubmit.",
            unit_name=unit_label,
            department=unit.department if unit else "",
            division=unit.division if unit else "",
            status=status.value,
            actor_name=manager,
            timestamp=s.updated_at.isoformat(),
            position_count=count,
        )

    if status == ObjectiveSetStatus.director_approved_and_activated_to_vp and UserRole.vp in actor.roles:
        return NotificationOut(
            id=f"set-{s.id}-vp",
            set_id=s.id,
            title="VP approval required",
            message=f"Unit Director approved {pos_label} for {unit_label}. Waiting for your VP approval.",
            unit_name=unit_label,
            department=unit.department if unit else "",
            division=unit.division if unit else "",
            status=status.value,
            actor_name=manager,
            timestamp=s.updated_at.isoformat(),
            position_count=count,
        )

    if status == ObjectiveSetStatus.director_rejected_to_manager and UserRole.manager in actor.roles:
        return NotificationOut(
            id=f"set-{s.id}-manager-reject",
            set_id=s.id,
            title="Objectives returned",
            message=f"Director rejected {pos_label} for {unit_label}. Please revise and resubmit.",
            unit_name=unit_label,
            department=unit.department if unit else "",
            division=unit.division if unit else "",
            status=status.value,
            actor_name=manager,
            timestamp=s.updated_at.isoformat(),
            position_count=count,
        )

    if status == ObjectiveSetStatus.sent_to_pms and UserRole.pms in actor.roles:
        return NotificationOut(
            id=f"set-{s.id}-pms",
            set_id=s.id,
            title="New package in PMS register",
            message=f"VP sent {pos_label} for {unit_label} to the PMS register.",
            unit_name=unit_label,
            department=unit.department if unit else "",
            division=unit.division if unit else "",
            status=status.value,
            actor_name=manager,
            timestamp=s.updated_at.isoformat(),
            position_count=count,
        )

    return None


@router.get("", response_model=NotificationsResponse)
def list_notifications(
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> NotificationsResponse:
    wanted: set[ObjectiveSetStatus] = set()
    for role in actor.roles:
        wanted |= _statuses_for_role(role)

    out: list[NotificationOut] = []
    if not wanted:
        return NotificationsResponse(unread_count=0, notifications=[])

    # Sets that have any position in a wanted status (or legacy rollup match).
    set_ids = {
        row.set_id
        for row in db.query(PositionObjectiveStatus)
        .filter(PositionObjectiveStatus.status.in_(list(wanted)))
        .all()
    }
    legacy = (
        db.query(ObjectiveSet)
        .filter(ObjectiveSet.status.in_(list(wanted)))
        .all()
    )
    set_ids |= {s.id for s in legacy}

    if not set_ids:
        return NotificationsResponse(unread_count=0, notifications=[])

    rows = (
        db.query(ObjectiveSet)
        .filter(ObjectiveSet.id.in_(list(set_ids)))
        .order_by(ObjectiveSet.updated_at.desc())
        .all()
    )
    for s in rows:
        try:
            assert_scope_for_set(db, actor, s)
        except Exception:
            continue
        matching = _matching_positions(db, s.id, wanted)
        # Fall back to rollup-only sets with no position rows yet.
        if not matching and s.status in wanted:
            matching = [
                PositionObjectiveStatus(
                    set_id=s.id,
                    position_id=0,
                    status=s.status,
                    updated_at=s.updated_at,
                )
            ]
        note = _notification_for_set(db, actor, s, matching)
        if note is not None:
            out.append(note)

    out.sort(key=lambda n: n.timestamp, reverse=True)
    return NotificationsResponse(unread_count=len(out), notifications=out)
