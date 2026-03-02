"""Categories API router for managing transaction categories."""

import uuid
from typing import List, Optional
from datetime import datetime
from dateutil import parser as date_parser

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Category, Transaction

router = APIRouter(prefix="/api/categories", tags=["Categories"])


# Request Models
class CategoryCreate(BaseModel):
    name: str
    type: str  # INCOME, EXPENSE
    parent_id: Optional[str] = None
    description: Optional[str] = None
    icon_id: Optional[str] = None
    color_hex: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    parent_id: Optional[str] = None
    description: Optional[str] = None
    icon_id: Optional[str] = None
    color_hex: Optional[str] = None
    is_archived: Optional[bool] = None


class CategoryBatchUpsert(BaseModel):
    """Model for batch upserting categories from mobile sync."""
    id: str  # UUID from mobile
    name: str
    type: str  # INCOME, EXPENSE
    parent_id: Optional[str] = None
    description: Optional[str] = None
    icon_id: Optional[str] = None
    color_hex: Optional[str] = None
    is_archived: Optional[int] = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CategoryResponse(BaseModel):
    id: str
    name: str
    type: str
    parent_id: Optional[str]
    description: Optional[str]
    icon_id: Optional[str]
    color_hex: Optional[str]
    is_archived: int
    created_at: str
    updated_at: str


@router.get("", response_model=List[CategoryResponse])
async def get_categories(
    type: Optional[str] = None, 
    include_archived: bool = False,
    since: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all categories. Use 'since' parameter for incremental sync."""
    query = db.query(Category)
    
    if type:
        query = query.filter(Category.type == type)
    
    if not include_archived:
        query = query.filter(Category.is_archived == 0)
    
    # Filter by updated_at for incremental sync
    if since:
        try:
            since_dt = date_parser.parse(since)
            query = query.filter(Category.updated_at >= since_dt)
        except (ValueError, TypeError):
            pass  # Ignore invalid date format
        
    categories = query.order_by(Category.name).all()
    return [c.to_dict() for c in categories]


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: str, db: Session = Depends(get_db)):
    """Get single category."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category.to_dict()


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    """Create a new category."""
    if data.parent_id:
        parent = db.query(Category).filter(Category.id == data.parent_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="Parent category not found")

    category = Category(
        id=str(uuid.uuid4()),
        name=data.name,
        type=data.type,
        parent_id=data.parent_id,
        description=data.description,
        icon_id=data.icon_id,
        color_hex=data.color_hex
    )
    
    db.add(category)
    db.commit()
    db.refresh(category)
    return category.to_dict()


@router.post("/batch", response_model=List[CategoryResponse])
async def upsert_categories(
    categories: List[CategoryBatchUpsert],
    db: Session = Depends(get_db)
):
    """Batch upsert categories for sync. Updates existing or inserts new."""
    results = []
    
    for cat_data in categories:
        existing = db.query(Category).filter(Category.id == cat_data.id).first()
        
        if existing:
            # Update if mobile version is newer
            mobile_updated = None
            if cat_data.updated_at:
                try:
                    mobile_updated = date_parser.parse(cat_data.updated_at)
                except (ValueError, TypeError):
                    mobile_updated = None
            
            # Update if mobile has newer timestamp or no timestamp comparison possible
            if mobile_updated is None or existing.updated_at is None or mobile_updated > existing.updated_at:
                existing.name = cat_data.name
                existing.type = cat_data.type
                existing.parent_id = cat_data.parent_id
                existing.description = cat_data.description
                existing.icon_id = cat_data.icon_id
                existing.color_hex = cat_data.color_hex
                existing.is_archived = cat_data.is_archived or 0
                existing.updated_at = datetime.now()
            results.append(existing)
        else:
            # Insert new
            now = datetime.now()
            category = Category(
                id=cat_data.id,
                name=cat_data.name,
                type=cat_data.type,
                parent_id=cat_data.parent_id,
                description=cat_data.description,
                icon_id=cat_data.icon_id,
                color_hex=cat_data.color_hex,
                is_archived=cat_data.is_archived or 0,
                created_at=now,
                updated_at=now
            )
            db.add(category)
            results.append(category)
    
    db.commit()
    for cat in results:
        db.refresh(cat)
    
    return [c.to_dict() for c in results]


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str, 
    data: CategoryUpdate, 
    db: Session = Depends(get_db)
):
    """Update a category."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    update_dict = data.model_dump(exclude_unset=True)
    
    if "parent_id" in update_dict and update_dict["parent_id"]:
        if update_dict["parent_id"] == category_id:
            raise HTTPException(status_code=400, detail="Category cannot be its own parent")
        parent = db.query(Category).filter(Category.id == update_dict["parent_id"]).first()
        if not parent:
            raise HTTPException(status_code=400, detail="Parent category not found")

    if "is_archived" in update_dict:
        update_dict["is_archived"] = 1 if update_dict["is_archived"] else 0

    for field, value in update_dict.items():
        setattr(category, field, value)
    
    category.updated_at = datetime.now()
    db.commit()
    db.refresh(category)
    return category.to_dict()


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: str, db: Session = Depends(get_db)):
    """Delete a category (hard delete if no dependencies, otherwise soft delete)."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Check if used in transactions
    usage_count = db.query(Transaction).filter(Transaction.category_id == category_id).count()
    children_count = db.query(Category).filter(Category.parent_id == category_id).count()
    
    if usage_count > 0 or children_count > 0:
        # Soft delete
        category.is_archived = 1
        category.updated_at = datetime.now()
        db.commit()
    else:
        # Hard delete
        db.delete(category)
        db.commit()
    
    return None
