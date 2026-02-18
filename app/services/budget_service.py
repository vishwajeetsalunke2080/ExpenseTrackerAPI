"""Budget service for managing budget CRUD operations with usage tracking."""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, extract
from decimal import Decimal
from datetime import date as date_type, datetime
import calendar

from app.models.expense import Budget, Expense
from app.schemas.budget import BudgetCreate, BudgetUpdate, BudgetResponse, BudgetUsage


class BudgetService:
    """Service for budget CRUD operations with monthly usage calculation."""
    
    def __init__(self, db: AsyncSession):
        """Initialize budget service with database session.
        
        Args:
            db: Async SQLAlchemy database session
        """
        self.db = db
    
    async def create_budget(self, budget_data: BudgetCreate) -> BudgetResponse:
        """Create a new budget that applies to every month.
        
        Validates that no existing budget exists for the same category.
        
        Args:
            budget_data: Budget creation data
            
        Returns:
            Created budget response
            
        Raises:
            ValueError: If budget already exists for the category
            
        Requirements: 14.1, 14.2
        """
        # Check if budget already exists for this category
        existing_query = select(Budget).where(Budget.category == budget_data.category)
        result = await self.db.execute(existing_query)
        existing_budget = result.scalar_one_or_none()
        
        if existing_budget:
            raise ValueError(
                f"Budget for category '{budget_data.category}' already exists. "
                f"Please update the existing budget instead."
            )
        
        # Create new budget
        db_budget = Budget(
            category=budget_data.category,
            amount_limit=budget_data.amount_limit
        )
        
        self.db.add(db_budget)
        await self.db.commit()
        await self.db.refresh(db_budget)
        
        return self._to_response(db_budget)
    
    async def get_budget(self, budget_id: int, month: Optional[int] = None, year: Optional[int] = None) -> Optional[BudgetResponse]:
        """Retrieve budget by ID with calculated usage for specified month.
        
        Args:
            budget_id: Budget ID
            month: Month to calculate usage for (defaults to current month)
            year: Year to calculate usage for (defaults to current year)
            
        Returns:
            Budget response with usage or None if not found
            
        Requirements: 14.3
        """
        result = await self.db.execute(
            select(Budget).where(Budget.id == budget_id)
        )
        budget = result.scalar_one_or_none()
        
        if not budget:
            return None
        
        return self._to_response(budget, month, year)
    
    async def list_budgets(
        self,
        category: Optional[str] = None,
        month: Optional[int] = None,
        year: Optional[int] = None
    ) -> List[BudgetResponse]:
        """List budgets with optional filters, including usage for specified month.
        
        Args:
            category: Optional category filter
            month: Month to calculate usage for (defaults to current month)
            year: Year to calculate usage for (defaults to current year)
            
        Returns:
            List of budget responses with usage information
            
        Requirements: 14.3, 15.2, 15.3
        """
        query = select(Budget)
        
        # Category filter
        if category:
            query = query.where(Budget.category == category)
        
        # Execute query
        result = await self.db.execute(query)
        budgets = result.scalars().all()
        
        # Return responses with usage for specified month
        return [self._to_response(budget, month, year) for budget in budgets]
    
    async def update_budget(self, budget_id: int, updates: BudgetUpdate) -> BudgetResponse:
        """Update budget.
        
        Args:
            budget_id: Budget ID to update
            updates: Budget update data
            
        Returns:
            Updated budget response
            
        Raises:
            ValueError: If budget not found
            
        Requirements: 14.4
        """
        # Get existing budget
        result = await self.db.execute(
            select(Budget).where(Budget.id == budget_id)
        )
        budget = result.scalar_one_or_none()
        
        if not budget:
            raise ValueError(f"Budget with id {budget_id} not found")
        
        # Update fields if provided
        if updates.category is not None:
            # Check if new category already has a budget
            existing_query = select(Budget).where(
                and_(
                    Budget.category == updates.category,
                    Budget.id != budget_id
                )
            )
            result = await self.db.execute(existing_query)
            if result.scalar_one_or_none():
                raise ValueError(f"Budget for category '{updates.category}' already exists")
            budget.category = updates.category
            
        if updates.amount_limit is not None:
            budget.amount_limit = updates.amount_limit
        
        await self.db.commit()
        await self.db.refresh(budget)
        
        return self._to_response(budget)
    
    async def delete_budget(self, budget_id: int) -> bool:
        """Delete budget.
        
        Args:
            budget_id: Budget ID to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If budget not found
            
        Requirements: 14.5
        """
        # Get existing budget
        result = await self.db.execute(
            select(Budget).where(Budget.id == budget_id)
        )
        budget = result.scalar_one_or_none()
        
        if not budget:
            raise ValueError(f"Budget with id {budget_id} not found")
        
        await self.db.delete(budget)
        await self.db.commit()
        
        return True
    
    async def calculate_usage(self, budget: Budget, month: Optional[int] = None, year: Optional[int] = None) -> BudgetUsage:
        """Calculate budget usage for a specific month.
        
        Args:
            budget: Budget model to calculate usage for
            month: Month to calculate (defaults to current month)
            year: Year to calculate (defaults to current year)
            
        Returns:
            BudgetUsage with amount spent, limit, percentage, and over-budget flag
            
        Requirements: 15.1, 15.4, 15.5
        """
        # Default to current month/year
        today = datetime.now().date()
        month = month if month else today.month
        year = year if year else today.year
        
        # Calculate start and end dates for the month
        start_date = date_type(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date_type(year, month, last_day)
        
        # Query expenses in the budget's category for the specified month
        query = select(func.sum(Expense.amount)).where(
            and_(
                Expense.category == budget.category,
                Expense.date >= start_date,
                Expense.date <= end_date
            )
        )
        
        result = await self.db.execute(query)
        total_spent = result.scalar()
        
        # Handle case where no expenses exist
        amount_spent = Decimal(str(total_spent)) if total_spent else Decimal('0.00')
        amount_limit = Decimal(str(budget.amount_limit))
        
        # Calculate percentage used
        if amount_limit > 0:
            percentage_used = (amount_spent / amount_limit) * Decimal('100')
        else:
            percentage_used = Decimal('0.00')
        
        # Check if over budget
        is_over_budget = amount_spent > amount_limit
        
        return BudgetUsage(
            amount_spent=amount_spent,
            amount_limit=amount_limit,
            percentage_used=percentage_used,
            is_over_budget=is_over_budget,
            month=month,
            year=year
        )
    
    def _to_response(self, budget: Budget, month: Optional[int] = None, year: Optional[int] = None) -> BudgetResponse:
        """Convert database model to response schema.
        
        Args:
            budget: Database budget model
            month: Month for usage calculation (defaults to current)
            year: Year for usage calculation (defaults to current)
            
        Returns:
            Budget response schema
        """
        return BudgetResponse(
            id=budget.id,
            category=budget.category,
            amount_limit=Decimal(str(budget.amount_limit)),
            created_at=budget.created_at,
            updated_at=budget.updated_at
        )
