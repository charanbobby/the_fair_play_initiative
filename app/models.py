"""
app/models.py
-------------
SQLAlchemy ORM models for the Fair Play Initiative.

Entities:
  Region, Organization, OrganizationRegion (M2M),
  Policy, Rule, Employee, PointHistory, AttendanceLog, Alert
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# ---------------------------------------------------------------------------
# Many-to-Many: Organization ↔ Region
# ---------------------------------------------------------------------------
organization_region = Table(
    "organization_region",
    Base.metadata,
    Column("organization_id", String, ForeignKey("organizations.id"), primary_key=True),
    Column("region_id", String, ForeignKey("regions.id"), primary_key=True),
)


# ---------------------------------------------------------------------------
# Region
# ---------------------------------------------------------------------------
class Region(Base):
    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, nullable=False)
    labor_laws: Mapped[str] = mapped_column(String, default="")

    # relationships
    organizations: Mapped[List["Organization"]] = relationship(
        "Organization", secondary=organization_region, back_populates="regions"
    )
    policies: Mapped[List["Policy"]] = relationship("Policy", back_populates="region")
    employees: Mapped[List["Employee"]] = relationship("Employee", back_populates="region")
    attendance_logs: Mapped[List["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="region"
    )


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------
class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # relationships
    regions: Mapped[List["Region"]] = relationship(
        "Region", secondary=organization_region, back_populates="organizations"
    )
    policies: Mapped[List["Policy"]] = relationship(
        "Policy", back_populates="organization", cascade="all, delete-orphan"
    )
    employees: Mapped[List["Employee"]] = relationship(
        "Employee", back_populates="organization"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="organization"
    )
    attendance_logs: Mapped[List["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="organization"
    )


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------
class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id"), nullable=False
    )
    region_id: Mapped[str] = mapped_column(
        String, ForeignKey("regions.id"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="policies"
    )
    region: Mapped["Region"] = relationship("Region", back_populates="policies")
    rules: Mapped[List["Rule"]] = relationship(
        "Rule", back_populates="policy", cascade="all, delete-orphan"
    )
    employees: Mapped[List["Employee"]] = relationship(
        "Employee", back_populates="policy"
    )
    attendance_logs: Mapped[List["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="policy"
    )


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------
class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("policies.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    condition: Mapped[str] = mapped_column(String, nullable=False)  # late|early|absence|no-call|...
    threshold: Mapped[int] = mapped_column(Integer, default=0)  # minutes; 0 = any
    points: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # relationships
    policy: Mapped[Optional["Policy"]] = relationship("Policy", back_populates="rules")


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------
class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    department: Mapped[str] = mapped_column(String, default="")
    position: Mapped[str] = mapped_column(String, default="")
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    points: Mapped[float] = mapped_column(Float, default=0.0)
    trend: Mapped[str] = mapped_column(String, default="stable")  # up|down|stable
    next_reset: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id"), nullable=False
    )
    region_id: Mapped[str] = mapped_column(
        String, ForeignKey("regions.id"), nullable=False
    )
    policy_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("policies.id"), nullable=True
    )

    # relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="employees"
    )
    region: Mapped["Region"] = relationship("Region", back_populates="employees")
    policy: Mapped[Optional["Policy"]] = relationship(
        "Policy", back_populates="employees"
    )
    point_history: Mapped[List["PointHistory"]] = relationship(
        "PointHistory",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="desc(PointHistory.date)",
    )
    attendance_logs: Mapped[List["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="employee", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# PointHistory
# ---------------------------------------------------------------------------
class PointHistory(Base):
    __tablename__ = "point_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # violation name or "Manual Override: ..."
    points: Mapped[float] = mapped_column(Float, nullable=False)  # positive=penalty, negative=deduction
    status: Mapped[str] = mapped_column(String, default="Active")  # Active|Excused|Approved
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # relationships
    employee: Mapped["Employee"] = relationship("Employee", back_populates="point_history")


# ---------------------------------------------------------------------------
# AttendanceLog
# ---------------------------------------------------------------------------
class AttendanceLog(Base):
    __tablename__ = "attendance_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id"), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id"), nullable=False
    )
    region_id: Mapped[str] = mapped_column(
        String, ForeignKey("regions.id"), nullable=False
    )
    policy_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("policies.id"), nullable=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_in: Mapped[str] = mapped_column(String, default="09:00 AM")
    scheduled_out: Mapped[str] = mapped_column(String, default="05:00 PM")
    actual_in: Mapped[str] = mapped_column(String, default="")
    actual_out: Mapped[str] = mapped_column(String, default="")
    violation: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    points: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="Compliant")  # Compliant|Violation|Active

    # relationships
    employee: Mapped["Employee"] = relationship("Employee", back_populates="attendance_logs")
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="attendance_logs"
    )
    region: Mapped["Region"] = relationship("Region", back_populates="attendance_logs")
    policy: Mapped[Optional["Policy"]] = relationship(
        "Policy", back_populates="attendance_logs"
    )


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------
class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("organizations.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(String, nullable=False)  # info|warning|danger|success
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # relationships
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization", back_populates="alerts"
    )
