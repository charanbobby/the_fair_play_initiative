"""
app/routers/regions.py
----------------------
CRUD endpoints for Region.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import RegionCreate, RegionResponse, RegionUpdate

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("/", response_model=List[RegionResponse])
def list_regions(db: Session = Depends(get_db)):
    return db.query(models.Region).all()


@router.post("/", response_model=RegionResponse, status_code=status.HTTP_201_CREATED)
def create_region(body: RegionCreate, db: Session = Depends(get_db)):
    if db.get(models.Region, body.id):
        raise HTTPException(status_code=400, detail=f"Region '{body.id}' already exists")
    region = models.Region(**body.model_dump())
    db.add(region)
    db.commit()
    db.refresh(region)
    return region


@router.get("/{region_id}", response_model=RegionResponse)
def get_region(region_id: str, db: Session = Depends(get_db)):
    region = db.get(models.Region, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    return region


@router.put("/{region_id}", response_model=RegionResponse)
def update_region(region_id: str, body: RegionUpdate, db: Session = Depends(get_db)):
    region = db.get(models.Region, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(region, field, value)
    db.commit()
    db.refresh(region)
    return region


@router.delete("/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_region(region_id: str, db: Session = Depends(get_db)):
    region = db.get(models.Region, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    db.delete(region)
    db.commit()
