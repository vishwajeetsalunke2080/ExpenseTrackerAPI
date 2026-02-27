"""Income service for managing income CRUD operations."""
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from decimal import Decimal

from app.models.expense import Income
from app.schemas.income import IncomeCreate, IncomeUpdate, IncomeResponse
from app.schemas.filter import ExpenseFilter


class IncomeService:
    """Service for income CRUD operations."""
    
    def __init__(self, db: AsyncSession, current_user):
        """Initialize income service with database session and current user.
        
        Args:
            db: Async SQLAlchemy database session
            current_user: Current authenticated user
        """
        self.db = db
        self.current_user = current_user
    
    async def create_income(self, income_data: IncomeCreate) -> IncomeResponse:
        """Create a new income record.
        
        Args:
            income_data: Income creation data
            
        Returns:
            Created income response
            
        Requirements: 13.1, 13.2
        """
        # Create new income with user_id from current_user
        db_income = Income(
            user_id=self.current_user.id,
            date=income_data.date,
            amount=income_data.amount,
            category=income_data.category,
            notes=income_data.notes
        )
        
        self.db.add(db_income)
        await self.db.commit()
        await self.db.refresh(db_income)
        
        return self._to_response(db_income)
    
    async def get_income(self, income_id: int) -> Optional[IncomeResponse]:
        """Retrieve income by ID.
        
        Args:
            income_id: Income ID
            
        Returns:
            Income response or None if not found
            
        Requirements: 13.5
        """
        # Query database with user_id filter
        result = await self.db.execute(
            select(Income).where(
                and_(
                    Income.id == income_id,
                    Income.user_id == self.current_user.id
                )
            )
        )
        income = result.scalar_one_or_none()
        
        if income:
            return self._to_response(income)
        
        return None
    
    async def update_income(self, income_id: int, updates: IncomeUpdate) -> IncomeResponse:
        """Update income.
        
        Args:
            income_id: Income ID to update
            updates: Income update data
            
        Returns:
            Updated income response
            
        Raises:
            ValueError: If income not found
            
        Requirements: 13.6, 13.8
        """
        # Get existing income with ownership verification
        result = await self.db.execute(
            select(Income).where(
                and_(
                    Income.id == income_id,
                    Income.user_id == self.current_user.id
                )
            )
        )
        income = result.scalar_one_or_none()
        
        if not income:
            raise ValueError(f"Income with id {income_id} not found")
        
        # Update fields if provided
        if updates.date is not None:
            income.date = updates.date
        if updates.amount is not None:
            income.amount = updates.amount
        if updates.category is not None:
            income.category = updates.category
        if updates.notes is not None:
            income.notes = updates.notes
        
        await self.db.commit()
        await self.db.refresh(income)
        
        return self._to_response(income)
    
    async def delete_income(self, income_id: int) -> bool:
        """Delete income.
        
        Args:
            income_id: Income ID to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If income not found
            
        Requirements: 13.7, 13.8
        """
        # Get existing income with ownership verification
        result = await self.db.execute(
            select(Income).where(
                and_(
                    Income.id == income_id,
                    Income.user_id == self.current_user.id
                )
            )
        )
        income = result.scalar_one_or_none()
        
        if not income:
            raise ValueError(f"Income with id {income_id} not found")
        
        await self.db.delete(income)
        await self.db.commit()
        
        return True
    
    async def list_income(self, filters: ExpenseFilter) -> Tuple[List[IncomeResponse], int]:
        """List income records with filtering and pagination.
        
        Supports filtering by:
        - Date range (start_date, end_date) - inclusive
        - Categories (list of category names) - OR logic within categories
        - Amount range (min_amount, max_amount) - inclusive
        - Multiple filters use AND logic
        
        Results are ordered by date descending (most recent first).
        
        Args:
            filters: ExpenseFilter with filter parameters and pagination
            
        Returns:
            Tuple of (list of income records, total count)
            
        Requirements: 13.4, 13.8
        """
        # Build query with filters - always filter by user_id
        query = select(Income).where(Income.user_id == self.current_user.id)
        conditions = []
        
        # Date range filter (inclusive)
        if filters.start_date:
            conditions.append(Income.date >= filters.start_date)
        if filters.end_date:
            conditions.append(Income.date <= filters.end_date)
        
        # Category filter (OR logic within categories)
        if filters.categories:
            conditions.append(Income.category.in_(filters.categories))
        
        # Amount range filter (inclusive)
        if filters.min_amount is not None:
            conditions.append(Income.amount >= filters.min_amount)
        if filters.max_amount is not None:
            conditions.append(Income.amount <= filters.max_amount)
        
        # Apply all conditions with AND logic
        if conditions:
            query = query.where(and_(*conditions))
        
        # Get total count for pagination metadata
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total_count = total_result.scalar()
        
        # Order by date descending (most recent first)
        query = query.order_by(Income.date.desc())
        
        # Apply pagination
        offset = (filters.page - 1) * filters.page_size
        query = query.offset(offset).limit(filters.page_size)
        
        # Execute query
        result = await self.db.execute(query)
        income_records = result.scalars().all()
        
        # Convert to response models
        income_responses = [self._to_response(inc) for inc in income_records]
        
        return income_responses, total_count
    
    def _to_response(self, income: Income) -> IncomeResponse:
        """Convert database model to response schema.
        
        Args:
            income: Database income model
            
        Returns:
            Income response schema
        """
        return IncomeResponse(
            id=income.id,
            date=income.date,
            amount=Decimal(str(income.amount)),
            category=income.category,
            notes=income.notes,
            created_at=income.created_at.date() if income.created_at else income.date,
            updated_at=income.updated_at.date() if income.updated_at else income.date
        )
