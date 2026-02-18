"""Account type service for managing payment methods and financial accounts."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.expense import AccountType
from app.schemas.account_type import AccountTypeCreate, AccountTypeUpdate, AccountTypeResponse


class AccountTypeService:
    """Service for account type CRUD operations."""
    
    def __init__(self, db: AsyncSession):
        """Initialize account type service with database session.
        
        Args:
            db: Async SQLAlchemy database session
        """
        self.db = db
    
    async def create_account_type(self, account_data: AccountTypeCreate) -> AccountTypeResponse:
        """Create a new account type, ensuring no duplicates.
        
        Args:
            account_data: Account type creation data
            
        Returns:
            Created account type response
            
        Raises:
            ValueError: If account type name already exists
        """
        # Check for duplicate name
        existing = await self._get_by_name(account_data.name)
        if existing:
            raise ValueError(f"Account type with name '{account_data.name}' already exists")
        
        # Create new account type
        db_account = AccountType(
            name=account_data.name,
            is_default=False
        )
        
        self.db.add(db_account)
        try:
            await self.db.commit()
            await self.db.refresh(db_account)
        except IntegrityError:
            await self.db.rollback()
            raise ValueError(f"Account type with name '{account_data.name}' already exists")
        
        return self._to_response(db_account)
    
    async def get_account_type(self, account_id: int) -> Optional[AccountTypeResponse]:
        """Retrieve account type by ID.
        
        Args:
            account_id: Account type ID
            
        Returns:
            Account type response or None if not found
        """
        result = await self.db.execute(
            select(AccountType).where(AccountType.id == account_id)
        )
        account = result.scalar_one_or_none()
        
        if account:
            return self._to_response(account)
        return None
    
    async def list_account_types(self) -> List[AccountTypeResponse]:
        """List all account types.
        
        Returns:
            List of account type responses ordered by name
        """
        query = select(AccountType).order_by(AccountType.name)
        
        result = await self.db.execute(query)
        accounts = result.scalars().all()
        
        return [self._to_response(acc) for acc in accounts]
    
    async def update_account_type(self, account_id: int, updates: AccountTypeUpdate) -> AccountTypeResponse:
        """Update account type name.
        
        Args:
            account_id: Account type ID to update
            updates: Account type update data
            
        Returns:
            Updated account type response
            
        Raises:
            ValueError: If account type not found or duplicate name
        """
        # Get existing account type
        result = await self.db.execute(
            select(AccountType).where(AccountType.id == account_id)
        )
        account = result.scalar_one_or_none()
        
        if not account:
            raise ValueError(f"Account type with id {account_id} not found")
        
        # Update name if provided
        if updates.name is not None:
            # Check for duplicate name (excluding current account type)
            existing = await self._get_by_name(updates.name)
            if existing and existing.id != account_id:
                raise ValueError(f"Account type with name '{updates.name}' already exists")
            
            account.name = updates.name
        
        try:
            await self.db.commit()
            await self.db.refresh(account)
        except IntegrityError:
            await self.db.rollback()
            raise ValueError(f"Account type with name '{updates.name}' already exists")
        
        return self._to_response(account)
    
    async def delete_account_type(self, account_id: int) -> bool:
        """Delete account type if not default.
        
        Args:
            account_id: Account type ID to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If account type not found or is default
        """
        # Get existing account type
        result = await self.db.execute(
            select(AccountType).where(AccountType.id == account_id)
        )
        account = result.scalar_one_or_none()
        
        if not account:
            raise ValueError(f"Account type with id {account_id} not found")
        
        if account.is_default:
            raise ValueError("Cannot delete default account type")
        
        await self.db.delete(account)
        await self.db.commit()
        
        return True
    
    async def initialize_defaults(self) -> None:
        """Initialize default account types on first run.
        
        Creates default account types: Cash, Card, UPI
        """
        defaults = ["Cash", "Card", "UPI"]
        
        for name in defaults:
            existing = await self._get_by_name(name)
            if not existing:
                account = AccountType(
                    name=name,
                    is_default=True
                )
                self.db.add(account)
        
        await self.db.commit()
    
    async def _get_by_name(self, name: str) -> Optional[AccountType]:
        """Get account type by name (case-sensitive).
        
        Args:
            name: Account type name
            
        Returns:
            Account type or None if not found
        """
        result = await self.db.execute(
            select(AccountType).where(AccountType.name == name)
        )
        return result.scalar_one_or_none()
    
    def _to_response(self, account: AccountType) -> AccountTypeResponse:
        """Convert database model to response schema.
        
        Args:
            account: Database account type model
            
        Returns:
            Account type response schema
        """
        return AccountTypeResponse(
            id=account.id,
            name=account.name,
            is_default=account.is_default
        )
