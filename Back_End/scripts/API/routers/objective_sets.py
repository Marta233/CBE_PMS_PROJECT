from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import (
    ActionType,
    ApprovalAction,
    Objective,
    ObjectiveSet,
    ObjectiveSetStatus,
    ObjectiveSetVersion,
    OrgUnit,
    PerformanceCycle,
    Position,
    PositionObjectiveStatus,
    ScopeType,
    UnitType,
    UserRole,
    UserRoleAssignment,
)
from .auth import get_current_actor
from ...workflow.permissions import ActorContext, assert_can, assert_scope_for_set, resolve_transition
from ...workflow.position_status import (
    can_actor_edit_position,
    get_or_create_position_status,
    list_position_statuses,
    position_statuses_payload,
    previous_objectives_by_position,
    refresh_set_rollup,
    should_apply_save_transition,
)


router = APIRouter(prefix="/objective-sets", tags=["objective-sets"])


class CreateObjectiveSetResponse(BaseModel):
    id: int
    unit_id: int
    cycle_id: int
    status: str
    current_version: int
    position_statuses: list[dict] = Field(default_factory=list)


class ObjectiveIn(BaseModel):
    position_id: int
    goal_statement: str = ""
    measurement: str = ""
    target: str = ""
    weight: int = 0
    category: str = ""
    tracking_source: str = ""
    time_frame: str = ""
    rating_guidance_json: dict | None = None
    bsc_link: str | None = None
    strategy_link: str | None = None
    los_alignment: str | None = None


class SaveObjectivesRequest(BaseModel):
    objectives: list[ObjectiveIn]
    snapshot_json: dict = Field(default_factory=dict)
    # Optional: only these positions get content/status updates; others are preserved.
    position_ids: list[int] | None = None


class ObjectiveOut(ObjectiveIn):
    id: int
    version_id: int


class ObjectiveSetOut(BaseModel):
    id: int
    unit_id: int
    manager_id: int
    cycle_id: int
    status: str
    current_version: int
    created_at: str
    updated_at: str
    unit: dict
    position_statuses: list[dict] = Field(default_factory=list)


class ObjectiveSetDetail(ObjectiveSetOut):
    version: dict | None = None
    objectives: list[ObjectiveOut] = Field(default_factory=list)


class PositionActionRequest(BaseModel):
    position_ids: list[int] = Field(default_factory=list)
    comment: str | None = None


class RejectRequest(BaseModel):
    comment: str
    position_ids: list[int] = Field(default_factory=list)


def _active_cycle(db: Session) -> PerformanceCycle:
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.is_active == True).one_or_none()  # noqa: E712
    if cycle is None:
        raise HTTPException(status_code=500, detail="No active performance cycle configured.")
    return cycle


def _actor_unit_scope(actor: ActorContext) -> Optional[int]:
    for a in actor.assignments:
        if a.role == UserRole.manager and a.scope_type == ScopeType.unit and a.scope_id is not None:
            return a.scope_id
    return None


def _manager_for_unit(db: Session, unit_id: int) -> Optional[int]:
    row = (
        db.query(UserRoleAssignment)
        .filter(
            UserRoleAssignment.role == UserRole.manager,
            UserRoleAssignment.scope_type == ScopeType.unit,
            UserRoleAssignment.scope_id == unit_id,
        )
        .first()
    )
    return row.user_id if row is not None else None


def _resolve_manager_id(db: Session, unit_id: int, actor: ActorContext) -> int:
    manager_id = _manager_for_unit(db, unit_id)
    if manager_id is not None:
        return manager_id
    return actor.user_id


def _assert_unit_in_scope(db: Session, actor: ActorContext, unit_id: int) -> None:
    probe = ObjectiveSet(
        unit_id=unit_id,
        manager_id=actor.user_id,
        cycle_id=1,
        status=ObjectiveSetStatus.draft,
        current_version=1,
    )
    assert_scope_for_set(db, actor, probe)


def _unit_dict(db: Session, unit_id: int) -> dict:
    u = db.query(OrgUnit).filter(OrgUnit.id == unit_id).one()
    return {
        "id": u.id,
        "name": u.name,
        "division": u.division,
        "department": u.department,
        "unit_type": u.unit_type.value,
        "parent_id": u.parent_id,
    }


def _set_out(db: Session, s: ObjectiveSet) -> ObjectiveSetOut:
    return ObjectiveSetOut(
        id=s.id,
        unit_id=s.unit_id,
        manager_id=s.manager_id,
        cycle_id=s.cycle_id,
        status=s.status.value,
        current_version=s.current_version,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
        unit=_unit_dict(db, s.unit_id),
        position_statuses=position_statuses_payload(db, s.id),
    )


def _record_action(
    db: Session,
    s: ObjectiveSet,
    actor: ActorContext,
    action: ActionType,
    from_status: ObjectiveSetStatus,
    to_status: ObjectiveSetStatus,
    comment: str | None = None,
    position_id: int | None = None,
) -> None:
    actor_role = actor.roles[0] if actor.roles else UserRole.manager
    db.add(
        ApprovalAction(
            objective_set_id=s.id,
            version_number=s.current_version,
            actor_id=actor.user_id,
            actor_role=actor_role,
            action=action,
            position_id=position_id,
            from_status=from_status,
            to_status=to_status,
            comment=comment,
            timestamp=datetime.utcnow(),
        )
    )


def _clone_objective(version_id: int, o: Objective) -> Objective:
    return Objective(
        version_id=version_id,
        position_id=o.position_id,
        goal_statement=o.goal_statement,
        measurement=o.measurement,
        target=o.target,
        weight=o.weight,
        category=o.category,
        tracking_source=o.tracking_source,
        time_frame=o.time_frame,
        rating_guidance_json=o.rating_guidance_json,
        bsc_link=o.bsc_link,
        strategy_link=o.strategy_link,
        los_alignment=o.los_alignment,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def _add_objective_from_in(version_id: int, row: ObjectiveIn) -> Objective:
    return Objective(
        version_id=version_id,
        position_id=row.position_id,
        goal_statement=row.goal_statement,
        measurement=row.measurement,
        target=row.target,
        weight=row.weight,
        category=row.category,
        tracking_source=row.tracking_source,
        time_frame=row.time_frame,
        rating_guidance_json=row.rating_guidance_json,
        bsc_link=row.bsc_link,
        strategy_link=row.strategy_link,
        los_alignment=row.los_alignment,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def _transition_positions(
    db: Session,
    s: ObjectiveSet,
    actor: ActorContext,
    action: ActionType,
    position_ids: list[int],
    comment: str | None = None,
) -> None:
    if not position_ids:
        raise HTTPException(status_code=422, detail="position_ids is required.")

    prev_by_pos = previous_objectives_by_position(db, s)
    unique_ids = list(dict.fromkeys(position_ids))

    for pid in unique_ids:
        if pid not in prev_by_pos and action != ActionType.save:
            # Activate/approve/reject require existing objectives for that position.
            raise HTTPException(
                status_code=422,
                detail=f"Position {pid} has no objectives on the current version.",
            )
        row = get_or_create_position_status(db, s.id, pid, default=ObjectiveSetStatus.draft)
        from_status = row.status
        tr = resolve_transition(db, actor, from_status, action)
        row.status = tr.to_status
        row.updated_at = datetime.utcnow()
        _record_action(
            db,
            s,
            actor,
            action,
            from_status,
            row.status,
            comment=comment,
            position_id=pid,
        )

    refresh_set_rollup(db, s)


@router.post("", response_model=CreateObjectiveSetResponse)
def create_objective_set(
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> CreateObjectiveSetResponse:
    assert_can(db, actor, ActionType.generate)
    unit_id = _actor_unit_scope(actor)
    if unit_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: no manager unit scope assigned.")

    cycle = _active_cycle(db)

    existing = (
        db.query(ObjectiveSet)
        .filter(ObjectiveSet.unit_id == unit_id, ObjectiveSet.cycle_id == cycle.id)
        .one_or_none()
    )
    if existing is not None:
        assert_scope_for_set(db, actor, existing)
        return CreateObjectiveSetResponse(
            id=existing.id,
            unit_id=existing.unit_id,
            cycle_id=existing.cycle_id,
            status=existing.status.value,
            current_version=existing.current_version,
            position_statuses=position_statuses_payload(db, existing.id),
        )

    s = ObjectiveSet(
        unit_id=unit_id,
        manager_id=actor.user_id,
        cycle_id=cycle.id,
        status=ObjectiveSetStatus.draft,
        current_version=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(s)
    db.flush()
    _record_action(db, s, actor, ActionType.generate, ObjectiveSetStatus.draft, ObjectiveSetStatus.draft)
    db.commit()
    return CreateObjectiveSetResponse(
        id=s.id,
        unit_id=s.unit_id,
        cycle_id=s.cycle_id,
        status=s.status.value,
        current_version=s.current_version,
        position_statuses=[],
    )


@router.get("/units", response_model=list[dict])
def list_units_in_scope(
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> list[dict]:
    assert_can(db, actor, ActionType.view)
    out: list[dict] = []
    units = db.query(OrgUnit).filter(OrgUnit.unit_type == UnitType.unit).order_by(OrgUnit.name.asc()).all()
    for u in units:
        try:
            _assert_unit_in_scope(db, actor, u.id)
        except HTTPException:
            continue
        out.append({
            "id": u.id,
            "name": u.name,
            "department": u.department,
            "division": u.division,
        })
    return out


@router.post("/by-unit/{unit_id}", response_model=CreateObjectiveSetResponse)
def get_or_create_set_for_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> CreateObjectiveSetResponse:
    assert_can(db, actor, ActionType.save)
    _assert_unit_in_scope(db, actor, unit_id)
    cycle = _active_cycle(db)

    existing = (
        db.query(ObjectiveSet)
        .filter(ObjectiveSet.unit_id == unit_id, ObjectiveSet.cycle_id == cycle.id)
        .one_or_none()
    )
    if existing is not None:
        assert_scope_for_set(db, actor, existing)
        return CreateObjectiveSetResponse(
            id=existing.id,
            unit_id=existing.unit_id,
            cycle_id=existing.cycle_id,
            status=existing.status.value,
            current_version=existing.current_version,
            position_statuses=position_statuses_payload(db, existing.id),
        )

    manager_id = _resolve_manager_id(db, unit_id, actor)
    s = ObjectiveSet(
        unit_id=unit_id,
        manager_id=manager_id,
        cycle_id=cycle.id,
        status=ObjectiveSetStatus.draft,
        current_version=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(s)
    db.flush()
    _record_action(db, s, actor, ActionType.save, ObjectiveSetStatus.draft, ObjectiveSetStatus.draft)
    db.commit()
    return CreateObjectiveSetResponse(
        id=s.id,
        unit_id=s.unit_id,
        cycle_id=s.cycle_id,
        status=s.status.value,
        current_version=s.current_version,
        position_statuses=[],
    )


@router.get("", response_model=list[ObjectiveSetOut])
def list_objective_sets(
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    cycle_id: Optional[int] = Query(default=None),
) -> list[ObjectiveSetOut]:
    assert_can(db, actor, ActionType.view)

    q = db.query(ObjectiveSet)
    if cycle_id is not None:
        q = q.filter(ObjectiveSet.cycle_id == cycle_id)

    wanted: ObjectiveSetStatus | None = None
    if status_filter is not None:
        try:
            wanted = ObjectiveSetStatus(status_filter)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid status filter.")

    out: list[ObjectiveSetOut] = []
    for s in q.order_by(ObjectiveSet.updated_at.desc()).all():
        try:
            assert_scope_for_set(db, actor, s)
        except HTTPException:
            continue
        statuses = list_position_statuses(db, s.id)
        if wanted is not None:
            # Include set if rollup matches OR any position is in that status.
            if s.status != wanted and not any(row.status == wanted for row in statuses):
                continue
        out.append(_set_out(db, s))
    return out


@router.get("/positions", response_model=list[dict])
def list_positions(
    unit_id: int,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> list[dict]:
    assert_can(db, actor, ActionType.view)

    temp_set = ObjectiveSet(unit_id=unit_id, manager_id=actor.user_id, cycle_id=_active_cycle(db).id)
    assert_scope_for_set(db, actor, temp_set)

    rows = db.query(Position).filter(Position.unit_id == unit_id).order_by(Position.title.asc()).all()
    return [{"id": r.id, "unit_id": r.unit_id, "title": r.title, "grade_level": r.grade_level} for r in rows]


@router.get("/{set_id}", response_model=ObjectiveSetDetail)
def get_objective_set(
    set_id: int,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> ObjectiveSetDetail:
    assert_can(db, actor, ActionType.view)
    s = db.query(ObjectiveSet).filter(ObjectiveSet.id == set_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Objective set not found.")
    assert_scope_for_set(db, actor, s)

    detail = ObjectiveSetDetail(**_set_out(db, s).model_dump(), version=None, objectives=[])

    v = (
        db.query(ObjectiveSetVersion)
        .filter(ObjectiveSetVersion.set_id == s.id, ObjectiveSetVersion.version_number == s.current_version)
        .one_or_none()
    )
    if v is not None:
        detail.version = {
            "id": v.id,
            "version_number": v.version_number,
            "submitted_by": v.submitted_by,
            "submitted_at": v.submitted_at.isoformat(),
            "snapshot_json": v.snapshot_json,
        }
        objs = db.query(Objective).filter(Objective.version_id == v.id).all()
        detail.objectives = [
            ObjectiveOut(
                id=o.id,
                version_id=o.version_id,
                position_id=o.position_id,
                goal_statement=o.goal_statement,
                measurement=o.measurement,
                target=o.target,
                weight=o.weight,
                category=o.category,
                tracking_source=o.tracking_source,
                time_frame=o.time_frame,
                rating_guidance_json=o.rating_guidance_json,
                bsc_link=o.bsc_link,
                strategy_link=o.strategy_link,
                los_alignment=o.los_alignment,
            )
            for o in objs
        ]

    return detail


@router.put("/{set_id}", response_model=ObjectiveSetOut)
def save_objective_set(
    set_id: int,
    req: SaveObjectivesRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> ObjectiveSetOut:
    assert_can(db, actor, ActionType.save)
    s = db.query(ObjectiveSet).filter(ObjectiveSet.id == set_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Objective set not found.")
    assert_scope_for_set(db, actor, s)

    prev_by_pos = previous_objectives_by_position(db, s)
    incoming_by_pos: dict[int, list[ObjectiveIn]] = {}
    for row in req.objectives:
        incoming_by_pos.setdefault(row.position_id, []).append(row)

    # Positions explicitly targeted for update; default = all incoming positions.
    target_ids = set(req.position_ids) if req.position_ids else set(incoming_by_pos.keys())

    # All positions that will appear in the new version.
    all_position_ids = set(prev_by_pos.keys()) | set(incoming_by_pos.keys())

    new_version = (s.current_version or 1) + 1
    v = ObjectiveSetVersion(
        set_id=s.id,
        version_number=new_version,
        submitted_by=actor.user_id,
        submitted_at=datetime.utcnow(),
        snapshot_json=req.snapshot_json or {},
    )
    db.add(v)
    db.flush()

    for pid in sorted(all_position_ids):
        existing_status = (
            db.query(PositionObjectiveStatus)
            .filter(PositionObjectiveStatus.set_id == s.id, PositionObjectiveStatus.position_id == pid)
            .one_or_none()
        )
        current = existing_status.status if existing_status else ObjectiveSetStatus.draft
        updating = pid in target_ids and pid in incoming_by_pos

        if updating and not can_actor_edit_position(actor, current) and existing_status is not None:
            # Preserve locked / out-of-scope positions from previous version.
            for o in prev_by_pos.get(pid, []):
                db.add(_clone_objective(v.id, o))
            continue

        if updating:
            for row in incoming_by_pos[pid]:
                db.add(_add_objective_from_in(v.id, row))
            pos_row = get_or_create_position_status(db, s.id, pid, default=ObjectiveSetStatus.draft)
            from_status = pos_row.status
            if should_apply_save_transition(actor, from_status):
                try:
                    tr = resolve_transition(db, actor, from_status, ActionType.save)
                    pos_row.status = tr.to_status
                except HTTPException:
                    # Keep status if no save transition (e.g. director editing in queue).
                    pass
            pos_row.updated_at = datetime.utcnow()
            _record_action(
                db, s, actor, ActionType.save, from_status, pos_row.status, position_id=pid
            )
        else:
            # Carry forward unchanged positions.
            for o in prev_by_pos.get(pid, []):
                db.add(_clone_objective(v.id, o))

    s.current_version = new_version
    refresh_set_rollup(db, s)
    db.commit()
    db.refresh(s)
    return _set_out(db, s)


@router.post("/{set_id}/activate", response_model=ObjectiveSetOut)
def activate_objective_set(
    set_id: int,
    req: PositionActionRequest | None = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> ObjectiveSetOut:
    assert_can(db, actor, ActionType.activate)
    s = db.query(ObjectiveSet).filter(ObjectiveSet.id == set_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Objective set not found.")
    assert_scope_for_set(db, actor, s)

    body = req or PositionActionRequest()
    position_ids = body.position_ids
    if not position_ids:
        raise HTTPException(status_code=422, detail="position_ids is required.")

    _transition_positions(db, s, actor, ActionType.activate, position_ids, comment=body.comment)
    db.commit()
    db.refresh(s)
    return _set_out(db, s)


@router.post("/{set_id}/approve", response_model=ObjectiveSetOut)
def approve_objective_set(
    set_id: int,
    req: PositionActionRequest | None = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> ObjectiveSetOut:
    assert_can(db, actor, ActionType.approve)
    s = db.query(ObjectiveSet).filter(ObjectiveSet.id == set_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Objective set not found.")
    assert_scope_for_set(db, actor, s)

    body = req or PositionActionRequest()
    position_ids = body.position_ids
    if not position_ids:
        raise HTTPException(status_code=422, detail="position_ids is required.")

    _transition_positions(db, s, actor, ActionType.approve, position_ids, comment=body.comment)
    db.commit()
    db.refresh(s)
    return _set_out(db, s)


@router.post("/{set_id}/reject", response_model=ObjectiveSetOut)
def reject_objective_set(
    set_id: int,
    req: RejectRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> ObjectiveSetOut:
    assert_can(db, actor, ActionType.reject)
    if not req.comment or not req.comment.strip():
        raise HTTPException(status_code=422, detail="Rejection comment is required.")
    if not req.position_ids:
        raise HTTPException(status_code=422, detail="position_ids is required.")

    s = db.query(ObjectiveSet).filter(ObjectiveSet.id == set_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Objective set not found.")
    assert_scope_for_set(db, actor, s)

    _transition_positions(
        db, s, actor, ActionType.reject, req.position_ids, comment=req.comment.strip()
    )
    db.commit()
    db.refresh(s)
    return _set_out(db, s)


@router.get("/{set_id}/history", response_model=dict)
def history(
    set_id: int,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> dict:
    assert_can(db, actor, ActionType.view)
    s = db.query(ObjectiveSet).filter(ObjectiveSet.id == set_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Objective set not found.")
    assert_scope_for_set(db, actor, s)

    actions = (
        db.query(ApprovalAction)
        .filter(ApprovalAction.objective_set_id == s.id)
        .order_by(ApprovalAction.timestamp.asc())
        .all()
    )
    versions = (
        db.query(ObjectiveSetVersion)
        .filter(ObjectiveSetVersion.set_id == s.id)
        .order_by(ObjectiveSetVersion.version_number.asc())
        .all()
    )
    return {
        "objective_set": _set_out(db, s).model_dump(),
        "actions": [
            {
                "id": a.id,
                "version_number": a.version_number,
                "actor_id": a.actor_id,
                "actor_role": a.actor_role.value,
                "action": a.action.value,
                "position_id": a.position_id,
                "from_status": a.from_status.value,
                "to_status": a.to_status.value,
                "comment": a.comment,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in actions
        ],
        "versions": [
            {
                "id": v.id,
                "version_number": v.version_number,
                "submitted_by": v.submitted_by,
                "submitted_at": v.submitted_at.isoformat(),
                "snapshot_json": v.snapshot_json,
            }
            for v in versions
        ],
        "position_statuses": position_statuses_payload(db, s.id),
    }
