from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class UnitType(str, enum.Enum):
    division = "division"
    department = "department"
    unit = "unit"


class ScopeType(str, enum.Enum):
    global_scope = "global"
    division = "division"
    department = "department"
    unit = "unit"


class UserRole(str, enum.Enum):
    manager = "manager"
    unit_director = "unit_director"
    vp = "vp"
    pms = "pms"
    hr_director = "hr_director"


class ActionType(str, enum.Enum):
    generate = "generate"
    save = "save"
    edit = "edit"
    activate = "activate"
    approve = "approve"
    reject = "reject"
    view = "view"


class ObjectiveSetStatus(str, enum.Enum):
    draft = "draft"
    saved = "saved"
    activated_to_director = "activated_to_director"
    director_rejected_to_manager = "director_rejected_to_manager"
    director_approved_and_activated_to_vp = "director_approved_and_activated_to_vp"
    vp_rejected_to_director = "vp_rejected_to_director"
    vp_approved_final = "vp_approved_final"
    sent_to_pms = "sent_to_pms"


class PerformanceCycle(Base):
    __tablename__ = "performance_cycles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class OrgUnit(Base):
    __tablename__ = "org_units"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("org_units.id"), nullable=True)

    division = Column(String(255), nullable=False, default="")
    department = Column(String(255), nullable=False, default="")
    unit_type = Column(Enum(UnitType), nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    parent = relationship("OrgUnit", remote_side=[id], backref="children")

    __table_args__ = (
        UniqueConstraint("name", "division", "department", "unit_type", name="uq_org_unit_identity"),
    )


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(Integer, ForeignKey("org_units.id"), nullable=False)
    title = Column(String(255), nullable=False)
    grade_level = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    unit = relationship("OrgUnit")

    __table_args__ = (
        UniqueConstraint("unit_id", "title", name="uq_position_unit_title"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=False, default="")
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class UserRoleAssignment(Base):
    __tablename__ = "user_role_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    scope_type = Column(Enum(ScopeType), nullable=False)
    scope_id = Column(Integer, ForeignKey("org_units.id"), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User")
    scope_unit = relationship("OrgUnit")

    __table_args__ = (
        UniqueConstraint("user_id", "role", "scope_type", "scope_id", name="uq_user_role_scope"),
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(Enum(UserRole), nullable=False)
    action = Column(Enum(ActionType), nullable=False)
    allowed = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("role", "action", name="uq_role_action"),
    )


class StatusTransition(Base):
    __tablename__ = "status_transitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_status = Column(Enum(ObjectiveSetStatus), nullable=False)
    action = Column(Enum(ActionType), nullable=False)
    actor_role = Column(Enum(UserRole), nullable=False)
    to_status = Column(Enum(ObjectiveSetStatus), nullable=False)

    __table_args__ = (
        UniqueConstraint("from_status", "action", "actor_role", name="uq_transition"),
    )


class UnitGenerationRule(Base):
    __tablename__ = "unit_generation_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(Integer, ForeignKey("org_units.id"), nullable=False, unique=True)
    generation_scope = Column(String(100), nullable=False, default="all_positions_in_unit")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    unit = relationship("OrgUnit")


class ObjectiveSet(Base):
    __tablename__ = "objective_sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(Integer, ForeignKey("org_units.id"), nullable=False)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    cycle_id = Column(Integer, ForeignKey("performance_cycles.id"), nullable=False)

    status = Column(Enum(ObjectiveSetStatus), nullable=False, default=ObjectiveSetStatus.draft)
    current_version = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    unit = relationship("OrgUnit")
    manager = relationship("User")
    cycle = relationship("PerformanceCycle")

    __table_args__ = (
        UniqueConstraint("unit_id", "cycle_id", name="uq_objective_set_unit_cycle"),
    )


class ObjectiveSetVersion(Base):
    __tablename__ = "objective_set_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    set_id = Column(Integer, ForeignKey("objective_sets.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    snapshot_json = Column(JSON, nullable=False, default=dict)

    objective_set = relationship("ObjectiveSet")
    submitter = relationship("User")

    __table_args__ = (
        UniqueConstraint("set_id", "version_number", name="uq_set_version"),
    )


class Objective(Base):
    __tablename__ = "objectives"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version_id = Column(Integer, ForeignKey("objective_set_versions.id"), nullable=False)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False)

    goal_statement = Column(Text, nullable=False, default="")
    measurement = Column(Text, nullable=False, default="")
    target = Column(Text, nullable=False, default="")
    weight = Column(Integer, nullable=False, default=0)
    category = Column(String(100), nullable=False, default="")
    tracking_source = Column(String(255), nullable=False, default="")
    time_frame = Column(String(50), nullable=False, default="")
    rating_guidance_json = Column(JSON, nullable=True)
    bsc_link = Column(Text, nullable=True)
    strategy_link = Column(Text, nullable=True)
    los_alignment = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    version = relationship("ObjectiveSetVersion")
    position = relationship("Position")


class PositionObjectiveStatus(Base):
    """Per-position workflow status within a unit objective set."""

    __tablename__ = "position_objective_statuses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    set_id = Column(Integer, ForeignKey("objective_sets.id"), nullable=False)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False)
    status = Column(Enum(ObjectiveSetStatus), nullable=False, default=ObjectiveSetStatus.draft)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    objective_set = relationship("ObjectiveSet")
    position = relationship("Position")

    __table_args__ = (
        UniqueConstraint("set_id", "position_id", name="uq_position_status_set_position"),
    )


class ApprovalAction(Base):
    __tablename__ = "approval_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    objective_set_id = Column(Integer, ForeignKey("objective_sets.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_role = Column(Enum(UserRole), nullable=False)
    action = Column(Enum(ActionType), nullable=False)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True)

    from_status = Column(Enum(ObjectiveSetStatus), nullable=False)
    to_status = Column(Enum(ObjectiveSetStatus), nullable=False)
    comment = Column(Text, nullable=True)

    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    objective_set = relationship("ObjectiveSet")
    actor = relationship("User")
    position = relationship("Position")

