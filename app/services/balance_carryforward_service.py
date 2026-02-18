"""Service for carrying forward monthly balance as savings."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, extract
from decimal import Decimal
from datetime import date, datetime
import calendar

from app.models.expense import Expense, Income


class BalanceCarryforwardService:
    """Service for automatically carrying forward monthly net balance as savings."""
    
    def __init__(self, db: AsyncSession):
        """Initialize balance carryforward service.
        
        Args:
            db: Async SQLAlchemy database session
        """
        self.db = db
        self.savings_category = "Savings (Carryforward)"
    
    async def calculate_monthly_balance(self, month: int, year: int) -> Decimal:
        """Calculate net balance for a specific month.
        
        Args:
            month: Month (1-12)
            year: Year
            
        Returns:
            Net balance (income - expenses) for the month
        """
        # Calculate start and end dates for the month
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)
        
        # Calculate total income for the month (excluding carryforward savings)
        income_query = select(func.sum(Income.amount)).where(
            and_(
                Income.date >= start_date,
                Income.date <= end_date,
                Income.category != self.savings_category
            )
        )
        result = await self.db.execute(income_query)
        total_income = result.scalar() or Decimal('0.00')
        
        # Calculate total expenses for the month
        expense_query = select(func.sum(Expense.amount)).where(
            and_(
                Expense.date >= start_date,
                Expense.date <= end_date
            )
        )
        result = await self.db.execute(expense_query)
        total_expenses = result.scalar() or Decimal('0.00')
        
        # Calculate net balance
        net_balance = Decimal(str(total_income)) - Decimal(str(total_expenses))
        
        return net_balance
    
    async def has_carryforward_for_month(self, month: int, year: int) -> bool:
        """Check if carryforward already exists for a specific month.
        
        Args:
            month: Month (1-12)
            year: Year
            
        Returns:
            True if carryforward entry exists for the month
        """
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)
        
        query = select(Income).where(
            and_(
                Income.category == self.savings_category,
                Income.date >= start_date,
                Income.date <= end_date
            )
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def carryforward_balance(self, from_month: int, from_year: int) -> Income:
        """Carry forward balance from one month to the next as savings income.
        
        Args:
            from_month: Source month (1-12)
            from_year: Source year
            
        Returns:
            Created income entry for the carryforward
            
        Raises:
            ValueError: If carryforward already exists for target month or balance is negative
        """
        # Calculate the target month (next month)
        if from_month == 12:
            to_month = 1
            to_year = from_year + 1
        else:
            to_month = from_month + 1
            to_year = from_year
        
        # Check if carryforward already exists for target month
        if await self.has_carryforward_for_month(to_month, to_year):
            raise ValueError(
                f"Balance carryforward already exists for {to_year}-{to_month:02d}"
            )
        
        # Calculate balance from source month
        balance = await self.calculate_monthly_balance(from_month, from_year)
        
        # Only carryforward positive balances
        if balance <= 0:
            raise ValueError(
                f"Cannot carryforward negative or zero balance. "
                f"Balance for {from_year}-{from_month:02d}: {balance}"
            )
        
        # Create income entry for the first day of target month
        carryforward_date = date(to_year, to_month, 1)
        
        income_entry = Income(
            date=carryforward_date,
            amount=balance,
            category=self.savings_category,
            notes=f"Carryforward from {from_year}-{from_month:02d}"
        )
        
        self.db.add(income_entry)
        await self.db.commit()
        await self.db.refresh(income_entry)
        
        return income_entry
    
    async def auto_carryforward_previous_month(self) -> Income:
        """Automatically carryforward balance from previous month to current month.
        
        Returns:
            Created income entry for the carryforward
            
        Raises:
            ValueError: If carryforward already exists or balance is negative
        """
        today = datetime.now().date()
        
        # Calculate previous month
        if today.month == 1:
            prev_month = 12
            prev_year = today.year - 1
        else:
            prev_month = today.month - 1
            prev_year = today.year
        
        return await self.carryforward_balance(prev_month, prev_year)
