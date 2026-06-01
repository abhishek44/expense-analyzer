"""Categories API router — 2-level hierarchy."""

import uuid
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category

router = APIRouter(prefix="/api/categories", tags=["Categories"])


class CategoryCreate(BaseModel):
    name: str
    level: int = 1
    parent_id: Optional[str] = None
    domain: Optional[str] = None
    color_hex: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    color_hex: Optional[str] = None
    is_archived: Optional[int] = None


@router.get("", summary="Get all categories")
async def get_categories(
    level: Optional[int] = None,
    domain: Optional[str] = None,
    include_children: bool = True,
    db: Session = Depends(get_db),
) -> list:
    """Return categories. If include_children=True, L1 entries include nested L2 children."""
    query = db.query(Category).filter(Category.is_archived == 0)

    if level:
        query = query.filter(Category.level == level)
    if domain:
        query = query.filter(Category.domain == domain)

    categories = query.order_by(Category.level, Category.name).all()

    if include_children and not level:
        l1_cats = [c for c in categories if c.level == 1]
        l2_cats = [c for c in categories if c.level == 2]
        l2_by_parent = {}
        for c in l2_cats:
            l2_by_parent.setdefault(c.parent_id, []).append(c.to_dict())

        result = []
        for c in l1_cats:
            d = c.to_dict()
            d["children"] = l2_by_parent.get(c.id, [])
            result.append(d)
        return result

    return [c.to_dict() for c in categories]


@router.get("/{category_id}", summary="Get single category")
async def get_category(category_id: str, db: Session = Depends(get_db)) -> dict:
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    d = cat.to_dict()
    if cat.level == 1:
        children = db.query(Category).filter(Category.parent_id == cat.id, Category.is_archived == 0).all()
        d["children"] = [c.to_dict() for c in children]
    return d


@router.post("", summary="Create category", status_code=201)
async def create_category(data: CategoryCreate, db: Session = Depends(get_db)) -> dict:
    if data.level == 2 and not data.parent_id:
        raise HTTPException(status_code=400, detail="L2 category requires a parent_id")

    if data.parent_id:
        parent = db.query(Category).filter(Category.id == data.parent_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="Parent category not found")
        if parent.level != 1:
            raise HTTPException(status_code=400, detail="Parent must be an L1 category")

    # Check uniqueness
    existing = db.query(Category).filter(Category.name == data.name, Category.parent_id == data.parent_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Category '{data.name}' already exists under this parent")

    now = datetime.now()
    cat = Category(
        id=str(uuid.uuid4()),
        name=data.name,
        level=data.level,
        parent_id=data.parent_id,
        domain=data.domain,
        color_hex=data.color_hex,
        created_at=now,
        updated_at=now,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat.to_dict()


@router.post("/batch", summary="Batch create categories", status_code=201)
async def batch_create_categories(categories: list[CategoryCreate], db: Session = Depends(get_db)) -> dict:
    created = []
    now = datetime.now()
    for data in categories:
        existing = db.query(Category).filter(Category.name == data.name, Category.parent_id == data.parent_id).first()
        if existing:
            continue
        cat = Category(
            id=str(uuid.uuid4()),
            name=data.name,
            level=data.level,
            parent_id=data.parent_id,
            domain=data.domain,
            color_hex=data.color_hex,
            created_at=now,
            updated_at=now,
        )
        db.add(cat)
        created.append(data.name)
    db.commit()
    return {"success": True, "created": len(created)}


@router.patch("/{category_id}", summary="Update category")
async def update_category(category_id: str, data: CategoryUpdate, db: Session = Depends(get_db)) -> dict:
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    update_dict = data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(cat, field, value)
    cat.updated_at = datetime.now()

    db.commit()
    db.refresh(cat)
    return cat.to_dict()


@router.delete("/{category_id}", summary="Delete category", status_code=204)
async def delete_category(category_id: str, db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    # If L1, also delete children
    if cat.level == 1:
        db.query(Category).filter(Category.parent_id == cat.id).delete()

    db.delete(cat)
    db.commit()
