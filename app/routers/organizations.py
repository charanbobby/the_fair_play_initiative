"""
app/routers/organizations.py
-----------------------------
CRUD endpoints for Organization (with nested region management).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import OrganizationCreate, OrganizationResponse, OrganizationUpdate

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _region_ids(org: models.Organization) -> List[str]:
    return [r.id for r in org.regions]


def _to_response(org: models.Organization) -> OrganizationResponse:
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        code=org.code,
        active=org.active,
        region_ids=_region_ids(org),
    )


@router.get("", response_model=List[OrganizationResponse])
def list_organizations(
    active_only: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Organization)
    if active_only is not None:
        q = q.filter(models.Organization.active == active_only)
    return [_to_response(o) for o in q.all()]


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(body: OrganizationCreate, db: Session = Depends(get_db)):
    if db.get(models.Organization, body.id):
        raise HTTPException(status_code=400, detail=f"Organization '{body.id}' already exists")

    org = models.Organization(id=body.id, name=body.name, code=body.code, active=body.active)
    for rid in body.region_ids:
        region = db.get(models.Region, rid)
        if not region:
            raise HTTPException(status_code=404, detail=f"Region '{rid}' not found")
        org.regions.append(region)

    db.add(org)
    db.commit()
    db.refresh(org)
    return _to_response(org)


@router.get("/{org_id}", response_model=OrganizationResponse)
def get_organization(org_id: str, db: Session = Depends(get_db)):
    org = db.get(models.Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _to_response(org)


@router.put("/{org_id}", response_model=OrganizationResponse)
def update_organization(
    org_id: str, body: OrganizationUpdate, db: Session = Depends(get_db)
):
    org = db.get(models.Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    for field, value in body.model_dump(exclude_none=True, exclude={"region_ids"}).items():
        setattr(org, field, value)

    if body.region_ids is not None:
        org.regions.clear()
        for rid in body.region_ids:
            region = db.get(models.Region, rid)
            if not region:
                raise HTTPException(status_code=404, detail=f"Region '{rid}' not found")
            org.regions.append(region)

    db.commit()
    db.refresh(org)
    return _to_response(org)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(org_id: str, db: Session = Depends(get_db)):
    org = db.get(models.Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    db.delete(org)
    db.commit()
