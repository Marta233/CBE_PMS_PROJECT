from __future__ import annotations

import os
import hashlib
import secrets
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from .database import DB_PATH, SessionLocal, engine
from .models import (
    ActionType,
    ApprovalAction,
    Objective,
    ObjectiveSet,
    ObjectiveSetStatus,
    ObjectiveSetVersion,
    PerformanceCycle,
    Position,
    PositionObjectiveStatus,
    RolePermission,
    ScopeType,
    StatusTransition,
    User,
    UserRole,
    UserRoleAssignment,
)
from .seed_org import seed_digital_banking
from .models import Base, OrgUnit, UnitType
from ..workflow.position_status import backfill_position_statuses, cleanup_bank_trainee_on_vp_sets
from sqlalchemy import text


PBKDF2_ITERATIONS = int(os.getenv("PMS_PBKDF2_ITERS", "200000"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters_s, salt_hex, hash_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
        return secrets.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def _ensure_dirs() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _seed_permissions(db: Session) -> None:
    role_actions = {
        UserRole.manager: {
            ActionType.generate,
            ActionType.save,
            ActionType.edit,
            ActionType.activate,
            ActionType.view,
        },
        UserRole.unit_director: {
            ActionType.generate,
            ActionType.save,
            ActionType.edit,
            ActionType.approve,
            ActionType.reject,
            ActionType.activate,
            ActionType.view,
        },
        UserRole.vp: {
            ActionType.save,
            ActionType.approve,
            ActionType.reject,
            ActionType.activate,
            ActionType.view,
        },
        UserRole.pms: {
            ActionType.view,
        },
        UserRole.hr_director: {
            ActionType.view,
        },
    }
    for role in UserRole:
        for action in ActionType:
            exists = (
                db.query(RolePermission)
                .filter(RolePermission.role == role, RolePermission.action == action)
                .one_or_none()
            )
            if exists is None:
                db.add(
                    RolePermission(
                        role=role,
                        action=action,
                        allowed=action in role_actions.get(role, set()),
                    )
                )
            else:
                should_allow = action in role_actions.get(role, set())
                if exists.allowed != should_allow:
                    exists.allowed = should_allow


def _seed_transitions(db: Session) -> None:
    transitions = [
        # Manager
        (ObjectiveSetStatus.draft, ActionType.save, UserRole.manager, ObjectiveSetStatus.saved),
        (ObjectiveSetStatus.saved, ActionType.save, UserRole.manager, ObjectiveSetStatus.saved),
        (ObjectiveSetStatus.saved, ActionType.activate, UserRole.manager, ObjectiveSetStatus.activated_to_director),
        (ObjectiveSetStatus.activated_to_director, ActionType.save, UserRole.manager, ObjectiveSetStatus.saved),
        (ObjectiveSetStatus.director_rejected_to_manager, ActionType.save, UserRole.manager, ObjectiveSetStatus.saved),
        # Per-position: manager may pull a single position back from VP only when that position is being edited.
        (ObjectiveSetStatus.director_approved_and_activated_to_vp, ActionType.save, UserRole.manager, ObjectiveSetStatus.saved),
        (ObjectiveSetStatus.draft, ActionType.save, UserRole.unit_director, ObjectiveSetStatus.saved),
        (ObjectiveSetStatus.saved, ActionType.save, UserRole.unit_director, ObjectiveSetStatus.saved),
        (ObjectiveSetStatus.director_approved_and_activated_to_vp, ActionType.save, UserRole.unit_director, ObjectiveSetStatus.saved),
        # Director
        (ObjectiveSetStatus.activated_to_director, ActionType.reject, UserRole.unit_director, ObjectiveSetStatus.director_rejected_to_manager),
        (ObjectiveSetStatus.activated_to_director, ActionType.activate, UserRole.unit_director, ObjectiveSetStatus.director_approved_and_activated_to_vp),
        (ObjectiveSetStatus.vp_rejected_to_director, ActionType.activate, UserRole.unit_director, ObjectiveSetStatus.director_approved_and_activated_to_vp),
        # Director may reject after VP return
        (ObjectiveSetStatus.vp_rejected_to_director, ActionType.reject, UserRole.unit_director, ObjectiveSetStatus.director_rejected_to_manager),
        # VP
        (ObjectiveSetStatus.director_approved_and_activated_to_vp, ActionType.reject, UserRole.vp, ObjectiveSetStatus.vp_rejected_to_director),
        (ObjectiveSetStatus.director_approved_and_activated_to_vp, ActionType.approve, UserRole.vp, ObjectiveSetStatus.vp_approved_final),
        (ObjectiveSetStatus.vp_approved_final, ActionType.activate, UserRole.vp, ObjectiveSetStatus.sent_to_pms),
    ]
    for from_s, action, role, to_s in transitions:
        exists = (
            db.query(StatusTransition)
            .filter(
                StatusTransition.from_status == from_s,
                StatusTransition.action == action,
                StatusTransition.actor_role == role,
            )
            .one_or_none()
        )
        if exists is None:
            db.add(
                StatusTransition(
                    from_status=from_s,
                    action=action,
                    actor_role=role,
                    to_status=to_s,
                )
            )


def _ensure_active_cycle(db: Session) -> PerformanceCycle:
    cycle = db.query(PerformanceCycle).filter(PerformanceCycle.is_active == True).one_or_none()  # noqa: E712
    if cycle is None:
        cycle = PerformanceCycle(name="Annual Cycle", fiscal_year=2026, is_active=True)
        db.add(cycle)
        db.flush()
    return cycle


def _create_user(db: Session, email: str, name: str, password: str) -> User:
    u = db.query(User).filter(User.email == email).one_or_none()
    if u is not None:
        return u
    u = User(
        email=email,
        name=name,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(u)
    db.flush()
    return u


def _ensure_scope_units(db: Session):
    division = db.query(OrgUnit).filter(OrgUnit.unit_type == UnitType.division, OrgUnit.name == "Digital Banking").one_or_none()
    dept = db.query(OrgUnit).filter(OrgUnit.unit_type == UnitType.department, OrgUnit.name == "Digital Banking Reconciliation and Dispute Management").one_or_none()
    unit = db.query(OrgUnit).filter(OrgUnit.unit_type == UnitType.unit, OrgUnit.name == "Merchant and Agent Reconciliation").one_or_none()
    return division, dept, unit


def _ensure_card_banking_units(db: Session):
    division = db.query(OrgUnit).filter(OrgUnit.unit_type == UnitType.division, OrgUnit.name == "Digital Banking").one_or_none()
    dept = db.query(OrgUnit).filter(
        OrgUnit.unit_type == UnitType.department,
        OrgUnit.division == "Digital Banking",
        OrgUnit.name == "Card Banking",
    ).one_or_none()
    unit = db.query(OrgUnit).filter(
        OrgUnit.unit_type == UnitType.unit,
        OrgUnit.division == "Digital Banking",
        OrgUnit.department == "Card Banking",
        OrgUnit.name == "Card Banking Business",
    ).one_or_none()
    return division, dept, unit


def _find_department(db: Session, department: str):
    """Department lookup within Digital Banking."""
    return db.query(OrgUnit).filter(
        OrgUnit.unit_type == UnitType.department,
        OrgUnit.division == "Digital Banking",
        OrgUnit.name == department,
    ).one_or_none()


def _find_unit(db: Session, department: str, unit_name: str):
    """Unit lookup within a Digital Banking department."""
    return db.query(OrgUnit).filter(
        OrgUnit.unit_type == UnitType.unit,
        OrgUnit.division == "Digital Banking",
        OrgUnit.department == department,
        OrgUnit.name == unit_name,
    ).one_or_none()


# Additional departments that get a director + one manager per unit.
# The director is scoped to the whole department (sees every unit in it).
# Each manager is scoped to a single unit within that department.
# VP/PMS/HR already cover these since their scope is division-wide / global.
_EXTRA_DEPARTMENTS = [
    (
        "Merchant and Agent Management",
        [
            ("Merchant Management", "manager.merchant@cbe.et", "Manager (Merchant Management)"),
            ("Agent Management", "manager.agent@cbe.et", "Manager (Agent Management)"),
            ("Digital Partners Relationship", "manager.digitalpartners@cbe.et", "Manager (Digital Partners Relationship)"),
        ],
        "director.merchant@cbe.et",
        "Director (Merchant and Agent Mgmt)",
    ),
    (
        "Mobile and Internet Banking",
        [
            ("Mobile Banking Business", "manager.mobilebanking@cbe.et", "Manager (Mobile Banking)"),
        ],
        "director.mobilebanking@cbe.et",
        "Director (Mobile and Internet Banking)",
    ),
    (
        "Mobile Money",
        [
            ("Mobile Money Business", "manager.mobilemoney@cbe.et", "Manager (Mobile Money)"),
        ],
        "director.mobilemoney@cbe.et",
        "Director (Mobile Money)",
    ),
]


def _seed_demo_users(db: Session, demo_password: str) -> None:
    manager = _create_user(db, "manager.recon@cbe.et", "Manager (Recon)", demo_password)
    director = _create_user(db, "director.recon@cbe.et", "Unit Director (Recon)", demo_password)
    manager_card = _create_user(db, "manager.card@cbe.et", "Manager (Card Banking)", demo_password)
    director_card = _create_user(db, "director.card@cbe.et", "Director (Card Banking)", demo_password)
    vp = _create_user(db, "vp.digital@cbe.et", "VP (Digital Banking)", demo_password)
    pms = _create_user(db, "pms@cbe.et", "PMS Department", demo_password)
    hr = _create_user(db, "hr.director@cbe.et", "HR Director", demo_password)

    division, dept, unit = _ensure_scope_units(db)
    card_division, card_dept, card_unit = _ensure_card_banking_units(db)

    if unit is not None:
        _assign_role(db, manager.id, UserRole.manager, ScopeType.unit, unit.id)
    if dept is not None:
        _assign_role(db, director.id, UserRole.unit_director, ScopeType.department, dept.id)
    if card_unit is not None:
        _assign_role(db, manager_card.id, UserRole.manager, ScopeType.unit, card_unit.id)
    if card_dept is not None:
        _assign_role(db, director_card.id, UserRole.unit_director, ScopeType.department, card_dept.id)
    if division is not None:
        _assign_role(db, vp.id, UserRole.vp, ScopeType.division, division.id)
    elif card_division is not None:
        _assign_role(db, vp.id, UserRole.vp, ScopeType.division, card_division.id)
    _assign_role(db, pms.id, UserRole.pms, ScopeType.global_scope, None)
    _assign_role(db, hr.id, UserRole.hr_director, ScopeType.global_scope, None)

    for dept_name, unit_managers, dir_email, dir_label in _EXTRA_DEPARTMENTS:
        dept_unit = _find_department(db, dept_name)
        director_extra = _create_user(db, dir_email, dir_label, demo_password)
        if dept_unit is not None:
            _assign_role(db, director_extra.id, UserRole.unit_director, ScopeType.department, dept_unit.id)
        for unit_name, mgr_email, mgr_label in unit_managers:
            unit = _find_unit(db, dept_name, unit_name)
            mgr = _create_user(db, mgr_email, mgr_label, demo_password)
            if unit is not None:
                _assign_role(db, mgr.id, UserRole.manager, ScopeType.unit, unit.id)


def _assign_role(db: Session, user_id: int, role: UserRole, scope_type: ScopeType, scope_id: int | None) -> None:
    exists = (
        db.query(UserRoleAssignment)
        .filter(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role == role,
            UserRoleAssignment.scope_type == scope_type,
            UserRoleAssignment.scope_id == scope_id,
        )
        .one_or_none()
    )
    if exists is None:
        db.add(
            UserRoleAssignment(
                user_id=user_id,
                role=role,
                scope_type=scope_type,
                scope_id=scope_id,
            )
        )


def init_db(frontend_types_path: Path | None = None) -> None:
    _ensure_dirs()
    Base.metadata.create_all(bind=engine)

    demo_password = os.getenv("PMS_DEMO_PASSWORD", "demo123")
    if frontend_types_path is None:
        # Resolve to repo root: Back_End/scripts/db/ -> Back_End -> repo
        frontend_types_path = (
            Path(__file__).resolve().parents[3]
            / "frontend"
            / "src"
            / "types"
            / "index.ts"
        )

    with SessionLocal() as db:
        _migrate_schema(db)
        # Org seed
        seed_digital_banking(db, frontend_types_path)

        # Config seed
        _seed_permissions(db)
        _seed_transitions(db)
        _ensure_active_cycle(db)

        _seed_demo_users(db, demo_password)
        _seed_demo_objective_sets(db)
        cleanup_bank_trainee_on_vp_sets(db)
        backfill_position_statuses(db)
        db.commit()


def _seed_demo_objective_sets(db: Session) -> None:
    """Intentionally empty — do not invent demo objectives.

    Real packages should come from AI generation / manager saves during the demo.
    Keep org users, permissions, and cycles seeded separately.
    """
    return


def _migrate_schema(db: Session) -> None:
    """Lightweight SQLite column adds for existing demo DBs."""
    cols = {row[1] for row in db.execute(text("PRAGMA table_info(approval_actions)")).fetchall()}
    if cols and "position_id" not in cols:
        db.execute(text("ALTER TABLE approval_actions ADD COLUMN position_id INTEGER"))


def reset_demo_objective_sets() -> None:
    """Clear all objective packages so the demo starts without seeded content."""
    _ensure_dirs()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.query(Objective).delete()
        db.query(ObjectiveSetVersion).delete()
        db.query(ApprovalAction).delete()
        db.query(PositionObjectiveStatus).delete()
        db.query(ObjectiveSet).delete()
        db.commit()


def init_db_if_needed() -> None:
    if DB_PATH.exists():
        return
    init_db()


def ensure_demo_users() -> None:
    """Upsert demo users/roles on every startup (safe for existing SQLite DBs)."""
    _ensure_dirs()
    Base.metadata.create_all(bind=engine)
    demo_password = os.getenv("PMS_DEMO_PASSWORD", "demo123")
    frontend_types_path = (
        Path(__file__).resolve().parents[3]
        / "frontend"
        / "src"
        / "types"
        / "index.ts"
    )
    with SessionLocal() as db:
        _migrate_schema(db)
        seed_digital_banking(db, frontend_types_path)
        _seed_permissions(db)
        _seed_transitions(db)
        _ensure_active_cycle(db)
        _seed_demo_users(db, demo_password)
        cleanup_bank_trainee_on_vp_sets(db)
        backfill_position_statuses(db)
        db.commit()