"""Income service for managing income CRUD operations with caching."""
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from decimal import Decimal
import hashlib
import json

from app.models.expense import Income
from app.schemas.income import IncomeCreate, IncomeUpdate, IncomeResponse
from app.schemas.filter import ExpenseFilter
from app.services.cache_service import CacheService


class IncomeService:
    """Service for income CRUD operations with caching support."""
    
    def __init__(self, db: AsyncSession, cache: CacheService):
        """Initialize income service with database session and cache.
        
        Args:
            db: Async SQLAlchemy database session
            cache: Cache service for Redis operations
        """
        self.db = db
        self.cache = cache
    
    async def create_income(self, income_data: IncomeCreate) -> IncomeResponse:
        """Create a new income record and invalidate relevant caches.
        
        Args:
            income_data: Income creation data
            
        Returns:
            Created income response
            
        Requirements: 13.1, 13.2
        """
        # Create new income
        db_income = Income(
            date=income_data.date,
            amount=income_data.amount,
            category=income_data.category,
            notes=income_data.notes
        )
        
        self.db.add(db_income)
        await self.db.commit()
        await self.db.refresh(db_income)
        
        # Invalidate list caches since we added a new income
        await self.cache.delete_pattern("income:filter:*")
        
        return self._to_response(db_income)
    
    async def get_income(self, income_id: int) -> Optional[IncomeResponse]:
        """Retrieve income by ID with caching.
        
        Args:
            income_id: Income ID
            
        Returns:
            Income response or None if not found
            
        Requirements: 13.5
        """
        # Check cache first
        cache_key = f"income:{income_id}"
        cached_data = await self.cache.get(cache_key)
        
        if cached_data:
            # Return cached data
            return IncomeResponse(**cached_data)
        
        # Query database
        result = await self.db.execute(
            select(Income).where(Income.id == income_id)
        )
        income = result.scalar_one_or_none()
        
        if income:
            response = self._to_response(income)
            # Cache the result
            await self.cache.set(cache_key, response.model_dump())
            return response
        
        return None
    
    async def update_income(self, income_id: int, updates: IncomeUpdate) -> IncomeResponse:
        """Update income and invalidate caches.
        
        Args:
            income_id: Income ID to update
            updates: Income update data
            
        Returns:
            Updated income response
            
        Raises:
            ValueError: If income not found
            
        Requirements: 13.6, 13.8
        """
        # Get existing income
        result = await self.db.execute(
            select(Income).where(Income.id == income_id)
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
        
        # Invalidate caches
        await self.cache.delete(f"income:{income_id}")
        await self.cache.delete_pattern("income:filter:*")
        
        return self._to_response(income)
    
    async def delete_income(self, income_id: int) -> bool:
        """Delete income and invalidate caches.
        
        Args:
            income_id: Income ID to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If income not found
            
        Requirements: 13.7, 13.8
        """
        # Get existing income
        result = await self.db.execute(
            select(Income).where(Income.id == income_id)
        )
        income = result.scalar_one_or_none()
        
        if not income:
            raise ValueError(f"Income with id {income_id} not found")
        
        await self.db.delete(income)
        await self.db.commit()
        
        # Invalidate caches
        await self.cache.delete(f"income:{income_id}")
        await self.cache.delete_pattern("income:filter:*")
        
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
        # Generate cache key from filter parameters
        cache_key = self._generate_filter_cache_key(filters)
        
        # Check cache first
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            income_records = [IncomeResponse(**inc) for inc in cached_data['income']]
            return income_records, cached_data['total']
        
        # Build query with filters
        query = select(Income)
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
        
        # Cache the results
        cache_data = {
            'income': [inc.model_dump() for inc in income_responses],
            'total': total_count
        }
        await self.cache.set(cache_key, cache_data)
        
        return income_responses, total_count
    
    def _generate_filter_cache_key(self, filters: ExpenseFilter) -> str:
        """Generate a cache key from filter parameters.
        
        Args:
            filters: ExpenseFilter with filter parameters
            
        Returns:
            Cache key string
        """
        # Create a dictionary of filter parameters
        filter_dict = {
            'start_date': filters.start_date.isoformat() if filters.start_date else None,
            'end_date': filters.end_date.isoformat() if filters.end_date else None,
            'categories': sorted(filters.categories) if filters.categories else None,
            'min_amount': str(filters.min_amount) if filters.min_amount is not None else None,
            'max_amount': str(filters.max_amount) if filters.max_amount is not None else None,
            'page': filters.page,
            'page_size': filters.page_size
        }
        
        # Generate hash from filter parameters
        filter_json = json.dumps(filter_dict, sort_keys=True)
        filter_hash = hashlib.md5(filter_json.encode()).hexdigest()
        
        return f"income:filter:{filter_hash}"
    
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
