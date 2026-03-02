"""
app/seed.py
-----------
Idempotent seed script — populates the database with demo data matching
the frontend's hard-coded sample state.

Run automatically on startup (skipped if data already exists).
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app import models


# ---------------------------------------------------------------------------
# Default data (mirrors the frontend JS defaultRules / defaultRegions)
# ---------------------------------------------------------------------------

DEFAULT_REGIONS = [
    {"id": "us-west", "name": "US West", "code": "US-W", "timezone": "America/Los_Angeles", "labor_laws": "California Labor Code"},
    {"id": "us-east", "name": "US East", "code": "US-E", "timezone": "America/New_York", "labor_laws": "Federal FLSA"},
    {"id": "eu-central", "name": "EU Central", "code": "EU-C", "timezone": "Europe/Berlin", "labor_laws": "EU Working Time Directive"},
    {"id": "apac", "name": "Asia Pacific", "code": "APAC", "timezone": "Asia/Singapore", "labor_laws": "Local Employment Acts"},
]

DEFAULT_ORGS = [
    {"id": "org-1", "name": "TechCorp Industries", "code": "TCORP", "active": True, "region_ids": ["us-west", "us-east"]},
    {"id": "org-2", "name": "Global Solutions Ltd", "code": "GSL", "active": True, "region_ids": ["eu-central"]},
    {"id": "org-3", "name": "Enterprise Holdings", "code": "ENT", "active": True, "region_ids": ["apac"]},
]

DEFAULT_RULES_TEMPLATE = [
    {"name": "Tardiness (> 7 min)", "condition": "late", "threshold": 7, "points": 0.5, "description": "Arriving more than 7 minutes after scheduled start time"},
    {"name": "Early Departure (> 15 min)", "condition": "early", "threshold": 15, "points": 0.5, "description": "Leaving more than 15 minutes before scheduled end time"},
    {"name": "Unexcused Absence", "condition": "absence", "threshold": 0, "points": 2.0, "description": "Missing scheduled shift without prior approval"},
    {"name": "No Call / No Show", "condition": "no-call", "threshold": 0, "points": 3.0, "description": "Failing to report absence without notification"},
]

DEFAULT_POLICIES = [
    {"id": "pol-1", "name": "TechCorp Standard Policy", "organization_id": "org-1", "region_id": "us-west", "multiplier": 1.0},
    {"id": "pol-2", "name": "TechCorp Remote Policy", "organization_id": "org-1", "region_id": "us-east", "multiplier": 0.8},
    {"id": "pol-3", "name": "Global Solutions EU Policy", "organization_id": "org-2", "region_id": "eu-central", "multiplier": 0.5},
    {"id": "pol-4", "name": "Enterprise APAC Standard", "organization_id": "org-3", "region_id": "apac", "multiplier": 1.0},
    {"id": "pol-5", "name": "Enterprise APAC Flexible", "organization_id": "org-3", "region_id": "apac", "multiplier": 1.0, "threshold_mult": 1.5},
]

FIRST_NAMES = ["James", "Maria", "Robert", "Jennifer", "Michael", "Linda", "William", "Patricia", "David", "Elizabeth", "Sarah", "Emily", "Emma", "Thomas", "Jessica"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Chen", "Ross", "Wilson", "Taylor", "Anderson"]
DEPARTMENTS = ["Engineering", "Sales", "Marketing", "HR", "Operations"]
POSITIONS = ["Manager", "Specialist", "Lead", "Associate"]


def seed(db: Session) -> None:
    """
    Populate demo data. Skips if organizations already exist (idempotent).
    """
    if db.query(models.Organization).count() > 0:
        return  # Already seeded

    print("seed: inserting demo data…")

    # Regions
    region_objects: dict[str, models.Region] = {}
    for r in DEFAULT_REGIONS:
        region = models.Region(**r)
        db.add(region)
        region_objects[r["id"]] = region

    db.flush()  # assign PKs so FK refs work

    # Organizations + region links
    org_objects: dict[str, models.Organization] = {}
    for o in DEFAULT_ORGS:
        org = models.Organization(id=o["id"], name=o["name"], code=o["code"], active=o["active"])
        for rid in o["region_ids"]:
            org.regions.append(region_objects[rid])
        db.add(org)
        org_objects[o["id"]] = org

    db.flush()

    # Policies + Rules
    policy_objects: dict[str, models.Policy] = {}
    for p in DEFAULT_POLICIES:
        policy = models.Policy(
            id=p["id"],
            name=p["name"],
            organization_id=p["organization_id"],
            region_id=p["region_id"],
            active=True,
            effective_date=date(2024, 1, 1),
        )
        mult = p.get("multiplier", 1.0)
        thresh_mult = p.get("threshold_mult", 1.0)
        for rt in DEFAULT_RULES_TEMPLATE:
            rule = models.Rule(
                name=rt["name"],
                condition=rt["condition"],
                threshold=int(rt["threshold"] * thresh_mult),
                points=round(rt["points"] * mult, 2),
                description=rt["description"],
                active=True,
            )
            policy.rules.append(rule)
        db.add(policy)
        policy_objects[p["id"]] = policy

    db.flush()

    # Policy → org mapping for employee assignment
    org_policies: dict[str, list[tuple[str, str]]] = {
        "org-1": [("pol-1", "us-west"), ("pol-2", "us-east")],
        "org-2": [("pol-3", "eu-central")],
        "org-3": [("pol-4", "apac"), ("pol-5", "apac")],
    }

    # Employees
    rng = random.Random(42)  # fixed seed for reproducibility
    violations = ["Tardiness", "Early Departure", "Unexcused Absence"]
    today = date.today()

    for org_def in DEFAULT_ORGS:
        org_id = org_def["id"]
        options = org_policies[org_id]
        num_employees = rng.randint(8, 14)

        for _ in range(num_employees):
            policy_id, region_id = rng.choice(options)
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            dept = rng.choice(DEPARTMENTS)
            pos = rng.choice(POSITIONS)
            points = round(rng.uniform(0, 8), 1)
            start_year = rng.randint(2020, 2023)
            start_month = rng.randint(1, 12)
            trend = rng.choice(["up", "down", "stable"])

            email = f"{first.lower()}.{last.lower()}.{rng.randint(100,999)}@{org_def['code'].lower()}.com"

            emp = models.Employee(
                first_name=first,
                last_name=last,
                email=email,
                department=dept,
                position=f"{dept} {pos}",
                start_date=date(start_year, start_month, 1),
                points=points,
                trend=trend,
                next_reset=today + timedelta(days=180),
                organization_id=org_id,
                region_id=region_id,
                policy_id=policy_id,
            )
            db.add(emp)
            db.flush()

            # Generate point history entries matching current point total
            remaining = points
            while remaining > 0:
                pts = 2.0 if remaining >= 2 else 0.5
                v = rng.choice(violations)
                days_ago = rng.randint(1, 90)
                history_entry = models.PointHistory(
                    employee_id=emp.id,
                    date=today - timedelta(days=days_ago),
                    type=v,
                    points=pts,
                    status="Active",
                )
                db.add(history_entry)
                remaining = round(remaining - pts, 1)

    db.flush()

    # Seed alerts
    seed_alerts = [
        {"organization_id": "org-1", "type": "warning", "message": "TechCorp: An employee is approaching the 8-point threshold (US-West)"},
        {"organization_id": "org-2", "type": "danger", "message": "Global Solutions: An employee exceeded 10 points — review required"},
        {"organization_id": "org-3", "type": "info", "message": "Enterprise Holdings: New policy rules extracted from handbook v2.3"},
        {"organization_id": "org-1", "type": "success", "message": "TechCorp: Monthly points reset completed for 12 employees"},
    ]
    for a in seed_alerts:
        db.add(models.Alert(**a))

    db.commit()
    print("seed: complete.")
