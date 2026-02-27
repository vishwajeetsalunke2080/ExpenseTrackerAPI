"""Expense service for managing expense CRUD operations."""
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from decimal import Decimal

from app.models.expense import Expense
from app.schemas.expense import ExpenseCreate, ExpenseUpdate, ExpenseResponse
from app.schemas.filter import ExpenseFilter


class ExpenseService:
    """Service for expense CRUD operations."""
    
    def __init__(self, db: AsyncSession, current_user):
        """Initialize expense service with database session and current user.

        Args:
            db: Async SQLAlchemy database session
            current_user: Current authenticated user
        """
        self.db = db
        self.current_user = current_user

    
    async def create_expense(self, expense_data: ExpenseCreate) -> ExpenseResponse:
        """Create a new expense.
        
        Args:
            expense_data: Expense creation data
            
        Returns:
            Created expense response
            
        Requirements: 1.1, 1.2, 1.5
        """
        # Create new expense with user_id from current_user
        db_expense = Expense(
            user_id=self.current_user.id,
            date=expense_data.date,
            amount=expense_data.amount,
            category=expense_data.category,
            account=expense_data.account,
            notes=expense_data.notes
        )
        
        self.db.add(db_expense)
        await self.db.commit()
        await self.db.refresh(db_expense)
        
        return self._to_response(db_expense)
    
    async def get_expense(self, expense_id: int) -> Optional[ExpenseResponse]:
        """Retrieve expense by ID.
        
        Args:
            expense_id: Expense ID
            
        Returns:
            Expense response or None if not found
            
        Requirements: 2.2
        """
        # Query database with user_id filter
        result = await self.db.execute(
            select(Expense).where(
                and_(
                    Expense.id == expense_id,
                    Expense.user_id == self.current_user.id
                )
            )
        )
        expense = result.scalar_one_or_none()
        
        if expense:
            return self._to_response(expense)
        
        return None
    
    async def update_expense(self, expense_id: int, updates: ExpenseUpdate) -> ExpenseResponse:
        """Update expense.
        
        Args:
            expense_id: Expense ID to update
            updates: Expense update data
            
        Returns:
            Updated expense response
            
        Raises:
            ValueError: If expense not found
            
        Requirements: 3.1, 3.4
        """
        # Get existing expense with ownership verification
        result = await self.db.execute(
            select(Expense).where(
                and_(
                    Expense.id == expense_id,
                    Expense.user_id == self.current_user.id
                )
            )
        )
        expense = result.scalar_one_or_none()
        
        if not expense:
            raise ValueError(f"Expense with id {expense_id} not found")
        
        # Update fields if provided
        if updates.date is not None:
            expense.date = updates.date
        if updates.amount is not None:
            expense.amount = updates.amount
        if updates.category is not None:
            expense.category = updates.category
        if updates.account is not None:
            expense.account = updates.account
        if updates.notes is not None:
            expense.notes = updates.notes
        
        await self.db.commit()
        await self.db.refresh(expense)
        
        return self._to_response(expense)
    
    async def delete_expense(self, expense_id: int) -> bool:
        """Delete expense.
        
        Args:
            expense_id: Expense ID to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If expense not found
            
        Requirements: 4.1, 4.3
        """
        # Get existing expense with ownership verification
        result = await self.db.execute(
            select(Expense).where(
                and_(
                    Expense.id == expense_id,
                    Expense.user_id == self.current_user.id
                )
            )
        )
        expense = result.scalar_one_or_none()
        
        if not expense:
            raise ValueError(f"Expense with id {expense_id} not found")
        
        await self.db.delete(expense)
        await self.db.commit()
        
        return True
    
    async def list_expenses(self, filters: ExpenseFilter) -> Tuple[List[ExpenseResponse], int]:
        """List expenses with filtering and pagination.
        
        Supports filtering by:
        - Date range (start_date, end_date) - inclusive
        - Categories (list of category names) - OR logic within categories
        - Accounts (list of account names) - OR logic within accounts
        - Amount range (min_amount, max_amount) - inclusive
        - Multiple filters use AND logic
        
        Results are ordered by date descending (most recent first).
        
        Args:
            filters: ExpenseFilter with filter parameters and pagination
            
        Returns:
            Tuple of (list of expenses, total count)
            
        Requirements: 2.1, 2.4, 5.1, 5.2, 5.3, 5.4, 5.5
        """
        # Build query with filters - always filter by user_id
        query = select(Expense).where(Expense.user_id == self.current_user.id)
        conditions = []
        
        # Date range filter (inclusive)
        if filters.start_date:
            conditions.append(Expense.date >= filters.start_date)
        if filters.end_date:
            conditions.append(Expense.date <= filters.end_date)

        # Category filter (OR logic within categories)
        if filters.categories:
            conditions.append(Expense.category.in_(filters.categories))
        
        # Account filter (OR logic within accounts)
        if filters.accounts:
            conditions.append(Expense.account.in_(filters.accounts))
        
        # Amount range filter (inclusive)
        if filters.min_amount is not None:
            conditions.append(Expense.amount >= filters.min_amount)
        if filters.max_amount is not None:
            conditions.append(Expense.amount <= filters.max_amount)
        
        # Apply all conditions with AND logic
        if conditions:
            query = query.where(and_(*conditions))
        
        # Get total count for pagination metadata
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total_count = total_result.scalar()
        
        # Order by date descending (most recent first)
        query = query.order_by(Expense.date.desc())
        
        # Apply pagination
        offset = (filters.page - 1) * filters.page_size
        query = query.offset(offset).limit(filters.page_size)
        
        # Execute query
        result = await self.db.execute(query)
        expenses = result.scalars().all()
        
        # Convert to response models
        expense_responses = [self._to_response(exp) for exp in expenses]
        
        return expense_responses, total_count
    
    def _to_response(self, expense: Expense) -> ExpenseResponse:
        """Convert database model to response schema.
        
        Args:
            expense: Database expense model
            
        Returns:
            Expense response schema
        """
        return ExpenseResponse(
            id=expense.id,
            date=expense.date,
            amount=Decimal(str(expense.amount)),
            category=expense.category,
            account=expense.account,
            notes=expense.notes,
            created_at=expense.created_at.date() if expense.created_at else expense.date,
            updated_at=expense.updated_at.date() if expense.updated_at else expense.date
        )
