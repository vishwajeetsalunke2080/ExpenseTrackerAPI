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
        
        Transaction Management:
        - This method MUST be called within an existing database transaction
        - It does NOT commit changes - the caller is responsible for transaction management
        - All changes will be committed when the caller's transaction commits
        - If any error occurs, the caller's transaction will rollback all changes atomically
        
        Args:
            user_id: The ID of the newly created user
        
        Raises:
            SQLAlchemyError: If database operations fail
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
        
        # Note: No flush() or commit() here - caller manages transaction lifecycle
        # This reduces one database round-trip and relies on caller's commit
