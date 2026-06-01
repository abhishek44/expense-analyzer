"""Pydantic schemas for shared request/response models."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: str | None = None
