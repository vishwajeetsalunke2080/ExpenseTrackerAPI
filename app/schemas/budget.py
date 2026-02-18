from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Optional


class BudgetBase(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
    amount_limit: Decimal = Field(..., gt=0, description="Monthly budget limit (must be positive)")


class BudgetCreate(BudgetBase):
    """Create a budget that applies to every month."""
    pass


class BudgetUpdate(BaseModel):
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    amount_limit: Optional[Decimal] = Field(None, gt=0)


class BudgetUsage(BaseModel):
    amount_spent: Decimal
    amount_limit: Decimal
    percentage_used: Decimal
    is_over_budget: bool
    month: int
    year: int


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    category: str
    amount_limit: Decimal
    created_at: datetime
    updated_at: datetime
