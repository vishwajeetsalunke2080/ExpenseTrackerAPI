from pydantic import BaseModel, Field, field_validator
from datetime import date as date_type
from decimal import Decimal
from typing import Optional, List


class ExpenseFilter(BaseModel):
    """Filter model for expense queries with pagination support.
    
    Supports filtering by:
    - Date range (start_date, end_date)
    - Categories (list of category names)
    - Accounts (list of account names)
    - Amount range (min_amount, max_amount)
    - Pagination (page, page_size)
    """
    
    start_date: Optional[date_type] = None
    end_date: Optional[date_type] = None
    categories: Optional[List[str]] = None
    accounts: Optional[List[str]] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    page: int = Field(1, ge=1, description="Page number (minimum 1)")
    page_size: int = Field(50, ge=1, le=100, description="Items per page (1-100)")

    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v, info):
        """Ensure end_date is not before start_date."""
        if v and info.data.get('start_date') and v < info.data['start_date']:
            raise ValueError('end_date must be after or equal to start_date')
        return v
