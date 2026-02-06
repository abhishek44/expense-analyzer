"""Categories API router for managing transaction categories."""

import uuid
from typing import List, Optional
from datetime import datetime

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
    db: Session = Depends(get_db)
):
    """List all categories."""
    query = db.query(Category)
    
    if type:
        query = query.filter(Category.type == type)
    
    if not include_archived:
        query = query.filter(Category.is_archived == 0)
        
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
