from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import date as date_type
from decimal import Decimal
from typing import Optional


class ExpenseBase(BaseModel):
    date: date_type = Field(..., description="Date when expense occurred")
    amount: Decimal = Field(..., gt=0, description="Expense amount (must be positive)")
    category: str = Field(..., min_length=1, max_length=100)
    account: str = Field(..., min_length=1, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    date: Optional[date_type] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    account: Optional[str] = Field(None, min_length=1, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)


class ExpenseResponse(ExpenseBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: date_type
    updated_at: date_type
