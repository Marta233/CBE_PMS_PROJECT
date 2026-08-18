"""Per-position workflow helpers for objective sets."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..db.models import (
    Objective,
    ObjectiveSet,
    ObjectiveSetStatus,
    ObjectiveSetVersion,
    PositionObjectiveStatus,
    UserRole,
)
from .permissions import ActorContext

# Lower index = higher priority for set-level rollup (needs attention first).
_ROLLUP_PRIORITY: list[ObjectiveSetStatus] = [
    ObjectiveSetStatus.director_rejected_to_manager,
    ObjectiveSetStatus.vp_rejected_to_director,
    ObjectiveSetStatus.activated_to_director,
    ObjectiveSetStatus.director_approved_and_activated_to_vp,
    ObjectiveSetStatus.saved,
    ObjectiveSetStatus.draft,
    ObjectiveSetStatus.vp_approved_final,
    ObjectiveSetStatus.sent_to_pms,
]

_LOCKED = frozenset(
    {
        ObjectiveSetStatus.vp_approved_final,
        ObjectiveSetStatus.sent_to_pms,
    }
)

# Manager must not rewrite / demote positions already past director approval.
_MANAGER_PRESERVE = frozenset(
    {
        ObjectiveSetStatus.director_approved_and_activated_to_vp,
        ObjectiveSetStatus.vp_rejected_to_director,
        ObjectiveSetStatus.vp_approved_final,
        ObjectiveSetStatus.sent_to_pms,
    }
)

# Reviewers may edit content in their queue without changing status via save.
_DIRECTOR_EDITABLE = frozenset(
    {
        ObjectiveSetStatus.activated_to_director,
        ObjectiveSetStatus.vp_rejected_to_director,
        ObjectiveSetStatus.draft,
        ObjectiveSetStatus.saved,
    }
)

_VP_EDITABLE = frozenset(
    {
        ObjectiveSetStatus.director_approved_and_activated_to_vp,
        ObjectiveSetStatus.vp_approved_final,
    }
)


def list_position_statuses(db: Session, set_id: int) -> list[PositionObjectiveStatus]:
    return (
        db.query(PositionObjectiveStatus)
        .filter(PositionObjectiveStatus.set_id == set_id)
        .order_by(PositionObjectiveStatus.position_id.asc())
        .all()
    )


def position_statuses_payload(db: Session, set_id: int) -> list[dict]:
    return [
        {"position_id": row.position_id, "status": row.status.value}
        for row in list_position_statuses(db, set_id)
    ]


def get_or_create_position_status(
    db: Session,
    set_id: int,
    position_id: int,
    default: ObjectiveSetStatus = ObjectiveSetStatus.draft,
) -> PositionObjectiveStatus:
    row = (
        db.query(PositionObjectiveStatus)
        .filter(
            PositionObjectiveStatus.set_id == set_id,
            PositionObjectiveStatus.position_id == position_id,
        )
        .one_or_none()
    )
    if row is not None:
        return row
    row = PositionObjectiveStatus(
        set_id=set_id,
        position_id=position_id,
        status=default,
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def rollup_status(db: Session, set_id: int, fallback: ObjectiveSetStatus = ObjectiveSetStatus.draft) -> ObjectiveSetStatus:
    rows = list_position_statuses(db, set_id)
    if not rows:
        return fallback
    best = rows[0].status
    best_rank = _ROLLUP_PRIORITY.index(best) if best in _ROLLUP_PRIORITY else len(_ROLLUP_PRIORITY)
    for row in rows[1:]:
        rank = _ROLLUP_PRIORITY.index(row.status) if row.status in _ROLLUP_PRIORITY else len(_ROLLUP_PRIORITY)
        if rank < best_rank:
            best = row.status
            best_rank = rank
    return best


def refresh_set_rollup(db: Session, s: ObjectiveSet) -> None:
    s.status = rollup_status(db, s.id, fallback=s.status or ObjectiveSetStatus.draft)
    s.updated_at = datetime.utcnow()


def position_ids_with_objectives(db: Session, s: ObjectiveSet) -> set[int]:
    v = (
        db.query(ObjectiveSetVersion)
        .filter(
            ObjectiveSetVersion.set_id == s.id,
            ObjectiveSetVersion.version_number == s.current_version,
        )
        .one_or_none()
    )
    if v is None:
        return set()
    rows = db.query(Objective.position_id).filter(Objective.version_id == v.id).distinct().all()
    return {r[0] for r in rows}


def previous_objectives_by_position(db: Session, s: ObjectiveSet) -> dict[int, list[Objective]]:
    v = (
        db.query(ObjectiveSetVersion)
        .filter(
            ObjectiveSetVersion.set_id == s.id,
            ObjectiveSetVersion.version_number == s.current_version,
        )
        .one_or_none()
    )
    if v is None:
        return {}
    out: dict[int, list[Objective]] = {}
    for o in db.query(Objective).filter(Objective.version_id == v.id).all():
        out.setdefault(o.position_id, []).append(o)
    return out


def can_actor_edit_position(actor: ActorContext, status: ObjectiveSetStatus) -> bool:
    if status in _LOCKED:
        return False
    if UserRole.manager in actor.roles and status not in _MANAGER_PRESERVE:
        return True
    if UserRole.unit_director in actor.roles and status in _DIRECTOR_EDITABLE:
        return True
    if UserRole.vp in actor.roles and status in _VP_EDITABLE:
        return True
    # HR / others: view only
    return False


def should_apply_save_transition(actor: ActorContext, status: ObjectiveSetStatus) -> bool:
    """Save may rewrite content for reviewers without moving status; managers use save transitions."""
    if status in _LOCKED:
        return False
    if UserRole.manager in actor.roles and status not in _MANAGER_PRESERVE:
        return True
    if UserRole.unit_director in actor.roles and status in (
        ObjectiveSetStatus.draft,
        ObjectiveSetStatus.saved,
    ):
        return True
    return False


def drop_position_objectives_from_current_version(
    db: Session,
    s: ObjectiveSet,
    position_id: int,
) -> int:
    """Remove a position's objectives from the current version and clear its status row."""
    v = (
        db.query(ObjectiveSetVersion)
        .filter(
            ObjectiveSetVersion.set_id == s.id,
            ObjectiveSetVersion.version_number == s.current_version,
        )
        .one_or_none()
    )
    deleted = 0
    if v is not None:
        deleted = (
            db.query(Objective)
            .filter(Objective.version_id == v.id, Objective.position_id == position_id)
            .delete(synchronize_session=False)
        )
    db.query(PositionObjectiveStatus).filter(
        PositionObjectiveStatus.set_id == s.id,
        PositionObjectiveStatus.position_id == position_id,
    ).delete(synchronize_session=False)
    return deleted


def cleanup_bank_trainee_on_vp_sets(db: Session) -> int:
    """One-time demo cleanup: drop Bank Trainee from packages already at VP.

    Keeps other positions at their VP-approved status so they are not demoted
    when position-level workflow is introduced.
    """
    from ..db.models import Position

    removed = 0
    sets = (
        db.query(ObjectiveSet)
        .filter(ObjectiveSet.status == ObjectiveSetStatus.director_approved_and_activated_to_vp)
        .all()
    )
    for s in sets:
        trainees = (
            db.query(Position)
            .filter(Position.unit_id == s.unit_id, Position.title == "Bank Trainee")
            .all()
        )
        for pos in trainees:
            # Only drop if this position currently has objectives on the set.
            if pos.id not in position_ids_with_objectives(db, s):
                continue
            drop_position_objectives_from_current_version(db, s, pos.id)
            removed += 1
        refresh_set_rollup(db, s)
    return removed


def backfill_position_statuses(db: Session) -> int:
    """Create missing position status rows from current version objectives + set.status."""
    created = 0
    sets = db.query(ObjectiveSet).all()
    for s in sets:
        pos_ids = position_ids_with_objectives(db, s)
        for pid in pos_ids:
            exists = (
                db.query(PositionObjectiveStatus)
                .filter(
                    PositionObjectiveStatus.set_id == s.id,
                    PositionObjectiveStatus.position_id == pid,
                )
                .one_or_none()
            )
            if exists is None:
                db.add(
                    PositionObjectiveStatus(
                        set_id=s.id,
                        position_id=pid,
                        status=s.status,
                        updated_at=datetime.utcnow(),
                    )
                )
                created += 1
        if pos_ids:
            refresh_set_rollup(db, s)
    return created
