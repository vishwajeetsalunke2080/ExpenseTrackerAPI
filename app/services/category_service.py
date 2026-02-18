"""Category service for managing expense and income categories."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.expense import Category, CategoryTypeEnum
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse, CategoryType


class CategoryService:
    """Service for category CRUD operations."""
    
    def __init__(self, db: AsyncSession):
        """Initialize category service with database session.
        
        Args:
            db: Async SQLAlchemy database session
        """
        self.db = db
    
    async def create_category(self, category_data: CategoryCreate) -> CategoryResponse:
        """Create a new category, ensuring no duplicates.
        
        Args:
            category_data: Category creation data
            
        Returns:
            Created category response
            
        Raises:
            ValueError: If category name already exists
        """
        # Check for duplicate name
        existing = await self._get_by_name(category_data.name)
        if existing:
            raise ValueError(f"Category with name '{category_data.name}' already exists")
        
        # Convert CategoryType enum to CategoryTypeEnum
        category_type_enum = CategoryTypeEnum.EXPENSE if category_data.type == CategoryType.EXPENSE else CategoryTypeEnum.INCOME
        
        # Create new category
        db_category = Category(
            name=category_data.name,
            type=category_type_enum,
            is_default=False
        )
        
        self.db.add(db_category)
        try:
            await self.db.commit()
            await self.db.refresh(db_category)
        except IntegrityError:
            await self.db.rollback()
            raise ValueError(f"Category with name '{category_data.name}' already exists")
        
        return self._to_response(db_category)
    
    async def get_category(self, category_id: int) -> Optional[CategoryResponse]:
        """Retrieve category by ID.
        
        Args:
            category_id: Category ID
            
        Returns:
            Category response or None if not found
        """
        result = await self.db.execute(
            select(Category).where(Category.id == category_id)
        )
        category = result.scalar_one_or_none()
        
        if category:
            return self._to_response(category)
        return None
    
    async def list_categories(self, category_type: Optional[CategoryType] = None) -> List[CategoryResponse]:
        """List all categories, optionally filtered by type.
        
        Args:
            category_type: Optional filter by category type (EXPENSE or INCOME)
            
        Returns:
            List of category responses
        """
        query = select(Category)
        
        if category_type:
            # Convert CategoryType to CategoryTypeEnum
            type_enum = CategoryTypeEnum.EXPENSE if category_type == CategoryType.EXPENSE else CategoryTypeEnum.INCOME
            query = query.where(Category.type == type_enum)
        
        query = query.order_by(Category.name)
        
        result = await self.db.execute(query)
        categories = result.scalars().all()
        
        return [self._to_response(cat) for cat in categories]
    
    async def update_category(self, category_id: int, updates: CategoryUpdate) -> CategoryResponse:
        """Update category name.
        
        Args:
            category_id: Category ID to update
            updates: Category update data
            
        Returns:
            Updated category response
            
        Raises:
            ValueError: If category not found or duplicate name
        """
        # Get existing category
        result = await self.db.execute(
            select(Category).where(Category.id == category_id)
        )
        category = result.scalar_one_or_none()
        
        if not category:
            raise ValueError(f"Category with id {category_id} not found")
        
        # Update name if provided
        if updates.name is not None:
            # Check for duplicate name (excluding current category)
            existing = await self._get_by_name(updates.name)
            if existing and existing.id != category_id:
                raise ValueError(f"Category with name '{updates.name}' already exists")
            
            category.name = updates.name
        
        try:
            await self.db.commit()
            await self.db.refresh(category)
        except IntegrityError:
            await self.db.rollback()
            raise ValueError(f"Category with name '{updates.name}' already exists")
        
        return self._to_response(category)
    
    async def delete_category(self, category_id: int) -> bool:
        """Delete category if not default.
        
        Args:
            category_id: Category ID to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If category not found or is default
        """
        # Get existing category
        result = await self.db.execute(
            select(Category).where(Category.id == category_id)
        )
        category = result.scalar_one_or_none()
        
        if not category:
            raise ValueError(f"Category with id {category_id} not found")
        
        if category.is_default:
            raise ValueError("Cannot delete default category")
        
        await self.db.delete(category)
        await self.db.commit()
        
        return True
    
    async def initialize_defaults(self) -> None:
        """Initialize default categories on first run.
        
        Creates default expense categories: Food, Travel, Groceries, Shopping, Other Expense
        Creates default income categories: Salary, Cash, Other Income
        
        Note: Using "Other Expense" and "Other Income" instead of just "Other" 
        to avoid unique constraint violation since category names must be unique across types.
        """
        # Default expense categories
        expense_defaults = ["Food", "Travel", "Groceries", "Shopping", "Other Expense"]
        for name in expense_defaults:
            existing = await self._get_by_name(name)
            if not existing:
                category = Category(
                    name=name,
                    type=CategoryTypeEnum.EXPENSE,
                    is_default=True
                )
                self.db.add(category)
        
        # Default income categories
        income_defaults = ["Salary", "Cash", "Other Income"]
        for name in income_defaults:
            existing = await self._get_by_name(name)
            if not existing:
                category = Category(
                    name=name,
                    type=CategoryTypeEnum.INCOME,
                    is_default=True
                )
                self.db.add(category)
        
        await self.db.commit()
    
    async def _get_by_name(self, name: str) -> Optional[Category]:
        """Get category by name (case-sensitive).
        
        Args:
            name: Category name
            
        Returns:
            Category or None if not found
        """
        result = await self.db.execute(
            select(Category).where(Category.name == name)
        )
        return result.scalar_one_or_none()
    
    def _to_response(self, category: Category) -> CategoryResponse:
        """Convert database model to response schema.
        
        Args:
            category: Database category model
            
        Returns:
            Category response schema
        """
        # Convert CategoryTypeEnum to CategoryType
        category_type = CategoryType.EXPENSE if category.type == CategoryTypeEnum.EXPENSE else CategoryType.INCOME
        
        return CategoryResponse(
            id=category.id,
            name=category.name,
            type=category_type,
            is_default=category.is_default
        )
