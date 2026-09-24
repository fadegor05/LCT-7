"""Pydantic-схемы объектов строительства."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SiteCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=500)


class SiteUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=500)


class SiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str | None
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
