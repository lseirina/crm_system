from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime

class OperatorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    is_active: bool = True
    max_load: int = Field(gt=0, le=1000, default=10)

class OperatorCreate(OperatorBase):
    pass

class OperatorResponse(OperatorBase):
    id: int
    created_at: datetime
    current_load: int = 0
    
    class Config:
        orm_mode = True

class LeadBase(BaseModel):
    external_id: str = Field(..., min_length=1)
    name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)

class LeadCreate(LeadBase):
    @validator('external_id')
    def external_id_not_empty(cls, v):
        return v.strip()

class LeadResponse(LeadBase):
    id: int
    created_at: datetime
    
    class Config:
        orm_mode = True

class SourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=200)

class SourceCreate(SourceBase):
    @validator('name')
    def name_not_empty(cls, v):
        return v.strip()

class SourceResponse(SourceBase):
    id: int
    created_at: datetime
    
    class Config:
        orm_mode = True

class OperatorSourceWeightBase(BaseModel):
    operator_id: int
    source_id: int
    weight: int = Field(gt=0, le=1000, default=10)

class OperatorSourceWeightCreate(OperatorSourceWeightBase):
    pass

class OperatorSourceWeightResponse(OperatorSourceWeightBase):
    id: int
    
    class Config:
        orm_mode = True

class ContactBase(BaseModel):
    source_id: int
    message: Optional[str] = Field(None, max_length=1000)

class ContactCreate(ContactBase):
    lead_external_id: str = Field(..., min_length=1)

    @validator('lead_external_id')
    def lead_external_id_not_empty(cls, v):
        return v.strip()

class ContactResponse(ContactBase):
    id: int
    lead_id: int
    operator_id: Optional[int]
    status: str
    created_at: datetime
    
    class Config:
        orm_mode = True

class DistributionConfig(BaseModel):
    source_id: int
    operators: List[OperatorSourceWeightCreate]