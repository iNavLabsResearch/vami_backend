from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Organisation(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class OrganisationCreate(BaseModel):
    name: str = Field(..., min_length=2)
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None


class OrganisationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2)
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None


class Pump(BaseModel):
    id: str
    organisation_id: str
    name: str
    location: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PumpCreate(BaseModel):
    organisation_id: str
    name: str
    location: Optional[str] = None


class Shift(BaseModel):
    id: str
    pump_id: str
    manager_id: Optional[str] = Field(default=None, description="Branch manager responsible for this shift")
    staff_name: Optional[str] = Field(default=None, description="Assigned staff name if not manager")
    start_time: datetime
    end_time: datetime
    created_at: datetime
    updated_at: datetime


class ShiftCreate(BaseModel):
    pump_id: str
    manager_id: Optional[str] = None
    staff_name: Optional[str] = None
    start_time: datetime
    end_time: datetime

