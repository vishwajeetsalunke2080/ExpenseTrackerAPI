"""Service for initializing new user accounts with default data."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.expense import Category, AccountType, CategoryTypeEnum


class UserOnboardingService:
    """Service for initializing new user accounts with default data."""
    
    DEFAULT_EXPENSE_CATEGORIES = [
        "Food & Dining",
        "Transportation",
        "Housing",
        "Utilities",
        "Entertainment",
        "Healthcare",
        "Shopping",
        "Personal Care",
        "Education",
        "Other Expenses"
    ]
    
    DEFAULT_INCOME_CATEGORIES = [
        "Salary",
        "Freelance",
        "Investment",
        "Gift",
        "Other Income"
    ]
    
    DEFAULT_ACCOUNT_TYPES = [
        "Cash",
        "Credit Card",
        "Debit Card",
        "Bank Transfer",
        "Digital Wallet"
    ]
    
    def __init__(self, db: AsyncSession):
        """Initialize the onboarding service.
        
        Args:
            db: Database session for executing queries
        """
        self.db = db
    
    async def initialize_user_defaults(self, user_id: int) -> None:
        """Create default categories and account types for a new user.
        
        This method creates a standard set of expense categories, income categories,
        and account types for a newly registered user. All created entities are marked
        with is_default=True to distinguish them from user-created entries.
        
        Args:
            user_id: The ID of the newly created user
        """
        # Create expense categories
        for category_name in self.DEFAULT_EXPENSE_CATEGORIES:
            category = Category(
                user_id=user_id,
                name=category_name,
                type=CategoryTypeEnum.EXPENSE,
                is_default=True
            )
            self.db.add(category)
        
        # Create income categories
        for category_name in self.DEFAULT_INCOME_CATEGORIES:
            category = Category(
                user_id=user_id,
                name=category_name,
                type=CategoryTypeEnum.INCOME,
                is_default=True
            )
            self.db.add(category)
        
        # Create account types
        for account_name in self.DEFAULT_ACCOUNT_TYPES:
            account_type = AccountType(
                user_id=user_id,
                name=account_name,
                is_default=True
            )
            self.db.add(account_type)
        
        await self.db.commit()
