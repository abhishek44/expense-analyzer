"""Pydantic schemas for request/response models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Response model for successful CSV upload."""
    
    success: bool = True
    message: str
    table_name: str
    rows_inserted: int
    columns: list[str]
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "message": "CSV uploaded successfully",
                "table_name": "expenses",
                "rows_inserted": 100,
                "columns": ["date", "amount", "category"]
            }
        }
    }


class ErrorResponse(BaseModel):
    """Response model for errors."""
    
    success: bool = False
    error: str
    detail: str | None = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": False,
                "error": "Invalid file format",
                "detail": "Only CSV files are allowed"
            }
        }
    }


class TableInfoResponse(BaseModel):
    """Response model for table information."""
    
    table_name: str
    row_count: int
    columns: list[dict[str, str]]
    sample_data: list[dict[str, Any]] = Field(default_factory=list)
