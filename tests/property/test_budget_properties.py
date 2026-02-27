"""Property-based tests for BudgetService.

These tests verify correctness properties across all valid inputs using Hypothesis.
Each test runs with max_examples=100 for comprehensive coverage as specified in the design.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import date, timedelta
from decimal import Decimal

from app.services.budget_service import BudgetService
from app.schemas.budget import BudgetCreate


# Custom strategies for generating test data
@st.composite
def valid_budget_data(draw):
    """Generate valid budget data with start_date before end_date.
    
    This strategy ensures:
    - start_date is before end_date
    - amount_limit is positive
    - category is non-empty
    """
    # Generate start date
    start_date = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2029, 12, 31)))
    
    # Generate end date that is after start date (at least 1 day later)
    days_diff = draw(st.integers(min_value=1, max_value=365))
    end_date = start_date + timedelta(days=days_diff)
    
    # Ensure end_date doesn't exceed reasonable bounds
    assume(end_date <= date(2030, 12, 31))
    
    return BudgetCreate(
        category=draw(st.text(
            min_size=1, 
            max_size=100, 
            alphabet=st.characters(exclude_characters='\x00', exclude_categories=('Cs',))
        )),
        amount_limit=draw(st.decimals(
            min_value=Decimal("0.01"), 
            max_value=Decimal("999999.99"), 
            places=2
        )),
        start_date=start_date,
        end_date=end_date
    )


# Property 30: Budget creation with valid date range
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(budget_data=valid_budget_data())
async def test_property_30_budget_creation_with_valid_date_range(budget_data, db_session):
    """
    Feature: expense-tracking-api, Property 30: Budget creation with valid date range
    
    **Validates: Requirements 14.1**
    
    For any budget with start_date before end_date and positive amount_limit,
    creating the budget should succeed and be retrievable with calculated usage information.
    """
    budget_service = BudgetService(db_session)
    
    # Verify preconditions
    assert budget_data.start_date < budget_data.end_date, "start_date must be before end_date"
    assert budget_data.amount_limit > 0, "amount_limit must be positive"
    
    # Create budget
    created = await budget_service.create_budget(budget_data)
    
    # Verify creation succeeded
    assert created is not None
    assert created.id is not None
    assert created.id > 0
    
    # Verify all fields match input
    assert created.category == budget_data.category
    assert created.amount_limit == budget_data.amount_limit
    assert created.start_date == budget_data.start_date
    assert created.end_date == budget_data.end_date
    
    # Verify usage information is present and calculated
    assert created.usage is not None
    assert created.usage.amount_spent >= 0
    assert created.usage.amount_limit == budget_data.amount_limit
    assert created.usage.percentage_used >= 0
    assert isinstance(created.usage.is_over_budget, bool)
    
    # Retrieve budget to verify persistence
    retrieved = await budget_service.get_budget(created.id)
    
    # Verify retrieval succeeded
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.category == budget_data.category
    assert retrieved.amount_limit == budget_data.amount_limit
    assert retrieved.start_date == budget_data.start_date
    assert retrieved.end_date == budget_data.end_date
    
    # Verify usage information is still present
    assert retrieved.usage is not None
    assert retrieved.usage.amount_spent >= 0
    assert retrieved.usage.amount_limit == budget_data.amount_limit
    
    # Clean up: delete the budget to avoid conflicts in subsequent iterations
    await budget_service.delete_budget(created.id)


# Property 31: Budget date range validation
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    category=st.text(
        min_size=1, 
        max_size=100, 
        alphabet=st.characters(exclude_characters='\x00', exclude_categories=('Cs',))
    ),
    amount_limit=st.decimals(
        min_value=Decimal("0.01"), 
        max_value=Decimal("999999.99"), 
        places=2
    ),
    start_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2029, 12, 31)),
    days_before=st.integers(min_value=1, max_value=365)
)
async def test_property_31_budget_date_range_validation(
    category, amount_limit, start_date, days_before, db_session
):
    """
    Feature: expense-tracking-api, Property 31: Budget date range validation
    
    **Validates: Requirements 14.6**
    
    For any budget where end_date is before start_date, the API should reject
    the creation request and return a validation error.
    """
    budget_service = BudgetService(db_session)
    
    # Create end_date that is before start_date
    end_date = start_date - timedelta(days=days_before)
    
    # Verify precondition: end_date is indeed before start_date
    assert end_date < start_date, "end_date must be before start_date for this test"
    
    # Attempt to create budget with invalid date range
    # This should raise a validation error from Pydantic
    with pytest.raises(ValueError) as exc_info:
        invalid_budget = BudgetCreate(
            category=category,
            amount_limit=amount_limit,
            start_date=start_date,
            end_date=end_date
        )
    
    # Verify the error message indicates date range validation failure
    error_message = str(exc_info.value)
    assert "end_date must be after start_date" in error_message.lower() or \
           "end_date" in error_message.lower(), \
           f"Expected date range validation error, got: {error_message}"


# Property 32: Budget amount validation
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    category=st.text(
        min_size=1, 
        max_size=100, 
        alphabet=st.characters(exclude_characters='\x00', exclude_categories=('Cs',))
    ),
    amount_limit=st.one_of(
        st.just(Decimal("0")),  # Zero
        st.decimals(
            min_value=Decimal("-999999.99"),
            max_value=Decimal("-0.01"),
            places=2
        )  # Negative values
    ),
    start_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2029, 12, 31)),
    days_after=st.integers(min_value=1, max_value=365)
)
async def test_property_32_budget_amount_validation(
    category, amount_limit, start_date, days_after, db_session
):
    """
    Feature: expense-tracking-api, Property 32: Budget amount validation
    
    **Validates: Requirements 14.7**
    
    For any budget with non-positive amount_limit, the API should reject
    the creation request and return a validation error.
    """
    budget_service = BudgetService(db_session)
    
    # Create valid end_date (after start_date)
    end_date = start_date + timedelta(days=days_after)
    
    # Ensure end_date doesn't exceed reasonable bounds
    assume(end_date <= date(2030, 12, 31))
    
    # Verify precondition: amount_limit is non-positive
    assert amount_limit <= 0, "amount_limit must be non-positive for this test"
    
    # Attempt to create budget with non-positive amount_limit
    # This should raise a validation error from Pydantic
    with pytest.raises(ValueError) as exc_info:
        invalid_budget = BudgetCreate(
            category=category,
            amount_limit=amount_limit,
            start_date=start_date,
            end_date=end_date
        )
    
    # Verify the error message indicates amount validation failure
    error_message = str(exc_info.value)
    assert "amount_limit" in error_message.lower() or \
           "greater than 0" in error_message.lower() or \
           "positive" in error_message.lower(), \
           f"Expected amount validation error, got: {error_message}"


# Property 33: Budget overlap detection
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    first_budget=valid_budget_data(),
    days_offset=st.integers(min_value=-180, max_value=180)
)
async def test_property_33_budget_overlap_detection(first_budget, days_offset, db_session):
    """
    Feature: expense-tracking-api, Property 33: Budget overlap detection
    
    **Validates: Requirements 14.2**
    
    For any category and time period, attempting to create a budget that overlaps
    with an existing budget for the same category should be rejected.
    """
    budget_service = BudgetService(db_session)
    
    try:
        # Create the first budget
        created_first = await budget_service.create_budget(first_budget)
        assert created_first is not None
        assert created_first.id is not None
        
        # Create a second budget that overlaps with the first one
        # We'll shift the dates by days_offset to create various overlap scenarios
        second_start = first_budget.start_date + timedelta(days=days_offset)
        second_end = first_budget.end_date + timedelta(days=days_offset)
        
        # Ensure dates are within reasonable bounds
        assume(second_start >= date(2020, 1, 1))
        assume(second_end <= date(2030, 12, 31))
        assume(second_start < second_end)
        
        # Check if the budgets overlap
        # Two ranges overlap if: start1 <= end2 AND end1 >= start2
        budgets_overlap = (
            first_budget.start_date <= second_end and
            first_budget.end_date >= second_start
        )
        
        second_budget = BudgetCreate(
            category=first_budget.category,  # Same category
            amount_limit=Decimal("500.00"),
            start_date=second_start,
            end_date=second_end
        )
        
        if budgets_overlap:
            # If budgets overlap, creation should fail with ValueError
            with pytest.raises(ValueError) as exc_info:
                await budget_service.create_budget(second_budget)
            
            # Verify the error message mentions overlap
            error_message = str(exc_info.value)
            assert "overlap" in error_message.lower() or \
                   "already exists" in error_message.lower(), \
                   f"Expected overlap error, got: {error_message}"
        else:
            # If budgets don't overlap, creation should succeed
            created_second = await budget_service.create_budget(second_budget)
            assert created_second is not None
            assert created_second.id is not None
            assert created_second.id != created_first.id
            
            # Clean up the second budget
            await budget_service.delete_budget(created_second.id)
        
        # Clean up the first budget
        await budget_service.delete_budget(created_first.id)
    finally:
        # Clean up database after each Hypothesis example to ensure test isolation
        await db_session.rollback()
        from app.database import Base
        await db_session.execute(Base.metadata.tables['budgets'].delete())


# Property 34: Budget usage calculation accuracy
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    budget_data=valid_budget_data(),
    num_expenses=st.integers(min_value=0, max_value=10),
    expense_amounts=st.lists(
        st.decimals(min_value=Decimal("0.01"), max_value=Decimal("9999.99"), places=2),
        min_size=0,
        max_size=10
    )
)
async def test_property_34_budget_usage_calculation_accuracy(
    budget_data, num_expenses, expense_amounts, db_session
):
    """
    Feature: expense-tracking-api, Property 34: Budget usage calculation accuracy
    
    **Validates: Requirements 15.1**
    
    For any budget and set of expenses in that budget's category and time period,
    the calculated usage amount should equal the sum of all matching expense amounts.
    """
    from app.services.expense_service import ExpenseService
    from app.services.cache_service import CacheService
    from app.schemas.expense import ExpenseCreate
    from datetime import timedelta
    import random
    
    # Ensure we have the right number of expense amounts
    expense_amounts = expense_amounts[:num_expenses]
    if len(expense_amounts) < num_expenses:
        expense_amounts.extend([Decimal("10.00")] * (num_expenses - len(expense_amounts)))
    
    budget_service = BudgetService(db_session)
    
    # Create a fake cache service for ExpenseService
    class FakeCacheService:
        async def get(self, key): return None
        async def set(self, key, value, ttl=None): pass
        async def delete(self, key): pass
        async def delete_pattern(self, pattern): pass
    
    expense_service = ExpenseService(db_session, FakeCacheService())
    
    # Create the budget
    created_budget = await budget_service.create_budget(budget_data)
    assert created_budget is not None
    
    # Calculate expected total
    expected_total = sum(expense_amounts)
    
    # Create expenses within the budget's category and time period
    created_expense_ids = []
    for amount in expense_amounts:
        # Generate a random date within the budget period
        days_range = (budget_data.end_date - budget_data.start_date).days
        if days_range > 0:
            random_days = random.randint(0, days_range)
        else:
            random_days = 0
        expense_date = budget_data.start_date + timedelta(days=random_days)
        
        expense_data = ExpenseCreate(
            date=expense_date,
            amount=amount,
            category=budget_data.category,  # Same category as budget
            account="TestAccount",
            notes="Test expense for budget usage"
        )
        
        created_expense = await expense_service.create_expense(expense_data)
        created_expense_ids.append(created_expense.id)
    
    # Retrieve the budget to get calculated usage
    retrieved_budget = await budget_service.get_budget(created_budget.id)
    
    # Verify usage calculation accuracy
    assert retrieved_budget is not None
    assert retrieved_budget.usage is not None
    
    # The calculated amount_spent should equal the sum of all matching expenses
    assert retrieved_budget.usage.amount_spent == expected_total, \
        f"Expected usage amount {expected_total}, but got {retrieved_budget.usage.amount_spent}"
    
    # Verify percentage calculation
    if budget_data.amount_limit > 0:
        expected_percentage = (expected_total / budget_data.amount_limit) * Decimal('100')
        assert retrieved_budget.usage.percentage_used == expected_percentage, \
            f"Expected percentage {expected_percentage}, but got {retrieved_budget.usage.percentage_used}"
    
    # Verify over-budget flag
    expected_over_budget = expected_total > budget_data.amount_limit
    assert retrieved_budget.usage.is_over_budget == expected_over_budget, \
        f"Expected is_over_budget={expected_over_budget}, but got {retrieved_budget.usage.is_over_budget}"
    
    # Clean up: delete expenses and budget
    for expense_id in created_expense_ids:
        await expense_service.delete_expense(expense_id)
    await budget_service.delete_budget(created_budget.id)


# Property 35: Budget usage recalculation on expense mutation
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    budget_data=valid_budget_data(),
    initial_amount=st.decimals(min_value=Decimal("10.00"), max_value=Decimal("500.00"), places=2),
    updated_amount=st.decimals(min_value=Decimal("10.00"), max_value=Decimal("500.00"), places=2),
    additional_amount=st.decimals(min_value=Decimal("10.00"), max_value=Decimal("500.00"), places=2)
)
async def test_property_35_budget_usage_recalculation_on_expense_mutation(
    budget_data, initial_amount, updated_amount, additional_amount, db_session
):
    """
    Feature: expense-tracking-api, Property 35: Budget usage recalculation on expense mutation
    
    **Validates: Requirements 15.4**
    
    For any budget, when expenses in that budget's category and time period are created,
    updated, or deleted, the budget usage should be automatically recalculated to reflect
    the changes.
    """
    from app.services.expense_service import ExpenseService
    from app.schemas.expense import ExpenseCreate, ExpenseUpdate
    from datetime import timedelta
    import random
    
    budget_service = BudgetService(db_session)
    
    # Create a fake cache service for ExpenseService
    class FakeCacheService:
        async def get(self, key): return None
        async def set(self, key, value, ttl=None): pass
        async def delete(self, key): pass
        async def delete_pattern(self, pattern): pass
    
    expense_service = ExpenseService(db_session, FakeCacheService())
    
    # Create the budget
    created_budget = await budget_service.create_budget(budget_data)
    assert created_budget is not None
    
    # Initial state: budget should have zero usage
    initial_budget = await budget_service.get_budget(created_budget.id)
    assert initial_budget.usage.amount_spent == Decimal('0.00')
    
    # Generate a random date within the budget period
    days_range = (budget_data.end_date - budget_data.start_date).days
    if days_range > 0:
        random_days = random.randint(0, days_range)
    else:
        random_days = 0
    expense_date = budget_data.start_date + timedelta(days=random_days)
    
    # Test 1: Create an expense - usage should increase
    expense_data = ExpenseCreate(
        date=expense_date,
        amount=initial_amount,
        category=budget_data.category,  # Same category as budget
        account="TestAccount",
        notes="Test expense for budget usage recalculation"
    )
    
    created_expense = await expense_service.create_expense(expense_data)
    
    # Retrieve budget and verify usage increased
    budget_after_create = await budget_service.get_budget(created_budget.id)
    assert budget_after_create.usage.amount_spent == initial_amount, \
        f"After creating expense with amount {initial_amount}, expected usage {initial_amount}, " \
        f"but got {budget_after_create.usage.amount_spent}"
    
    # Verify percentage calculation
    expected_percentage_after_create = (initial_amount / budget_data.amount_limit) * Decimal('100')
    assert budget_after_create.usage.percentage_used == expected_percentage_after_create
    
    # Test 2: Update the expense - usage should reflect the new amount
    expense_update = ExpenseUpdate(amount=updated_amount)
    await expense_service.update_expense(created_expense.id, expense_update)
    
    # Retrieve budget and verify usage changed to reflect update
    budget_after_update = await budget_service.get_budget(created_budget.id)
    assert budget_after_update.usage.amount_spent == updated_amount, \
        f"After updating expense to amount {updated_amount}, expected usage {updated_amount}, " \
        f"but got {budget_after_update.usage.amount_spent}"
    
    # Verify percentage calculation after update
    expected_percentage_after_update = (updated_amount / budget_data.amount_limit) * Decimal('100')
    assert budget_after_update.usage.percentage_used == expected_percentage_after_update
    
    # Test 3: Create another expense - usage should be sum of both expenses
    expense_data_2 = ExpenseCreate(
        date=expense_date,
        amount=additional_amount,
        category=budget_data.category,
        account="TestAccount",
        notes="Second test expense"
    )
    
    created_expense_2 = await expense_service.create_expense(expense_data_2)
    
    # Retrieve budget and verify usage is sum of both expenses
    expected_total = updated_amount + additional_amount
    budget_after_second_create = await budget_service.get_budget(created_budget.id)
    assert budget_after_second_create.usage.amount_spent == expected_total, \
        f"After creating second expense, expected usage {expected_total}, " \
        f"but got {budget_after_second_create.usage.amount_spent}"
    
    # Verify percentage calculation with both expenses
    expected_percentage_with_both = (expected_total / budget_data.amount_limit) * Decimal('100')
    assert budget_after_second_create.usage.percentage_used == expected_percentage_with_both
    
    # Test 4: Delete the first expense - usage should decrease
    await expense_service.delete_expense(created_expense.id)
    
    # Retrieve budget and verify usage decreased to only the second expense
    budget_after_delete = await budget_service.get_budget(created_budget.id)
    assert budget_after_delete.usage.amount_spent == additional_amount, \
        f"After deleting first expense, expected usage {additional_amount}, " \
        f"but got {budget_after_delete.usage.amount_spent}"
    
    # Verify percentage calculation after deletion
    expected_percentage_after_delete = (additional_amount / budget_data.amount_limit) * Decimal('100')
    assert budget_after_delete.usage.percentage_used == expected_percentage_after_delete
    
    # Test 5: Delete the second expense - usage should return to zero
    await expense_service.delete_expense(created_expense_2.id)
    
    # Retrieve budget and verify usage is back to zero
    budget_after_all_deleted = await budget_service.get_budget(created_budget.id)
    assert budget_after_all_deleted.usage.amount_spent == Decimal('0.00'), \
        f"After deleting all expenses, expected usage 0.00, " \
        f"but got {budget_after_all_deleted.usage.amount_spent}"
    
    # Verify percentage is zero
    assert budget_after_all_deleted.usage.percentage_used == Decimal('0.00')
    assert budget_after_all_deleted.usage.is_over_budget == False
    
    # Clean up: delete budget
    await budget_service.delete_budget(created_budget.id)


# Property 36: Budget over-budget flagging
@pytest.mark.asyncio
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    budget_data=valid_budget_data(),
    num_expenses=st.integers(min_value=1, max_value=10),
    expense_amounts=st.lists(
        st.decimals(min_value=Decimal("10.00"), max_value=Decimal("9999.99"), places=2),
        min_size=1,
        max_size=10
    )
)
async def test_property_36_budget_over_budget_flagging(
    budget_data, num_expenses, expense_amounts, db_session
):
    """
    Feature: expense-tracking-api, Property 36: Budget over-budget flagging
    
    **Validates: Requirements 15.5**
    
    For any budget where the total expenses exceed the amount_limit, the budget response
    should flag is_over_budget as true and percentage_used should exceed 100%.
    """
    from app.services.expense_service import ExpenseService
    from app.schemas.expense import ExpenseCreate
    from datetime import timedelta
    import random
    
    # Ensure we have the right number of expense amounts
    expense_amounts = expense_amounts[:num_expenses]
    if len(expense_amounts) < num_expenses:
        expense_amounts.extend([Decimal("10.00")] * (num_expenses - len(expense_amounts)))
    
    budget_service = BudgetService(db_session)
    
    # Create a fake cache service for ExpenseService
    class FakeCacheService:
        async def get(self, key): return None
        async def set(self, key, value, ttl=None): pass
        async def delete(self, key): pass
        async def delete_pattern(self, pattern): pass
    
    expense_service = ExpenseService(db_session, FakeCacheService())
    
    # Calculate total expenses
    total_expenses = sum(expense_amounts)
    
    # Ensure the total expenses exceed the budget limit
    # Set the budget limit to be less than the total expenses
    # Subtract a fixed amount to ensure it's always exceeded, avoiding rounding issues
    over_budget_limit = total_expenses - Decimal("5.00")
    
    # Ensure the limit is positive
    assume(over_budget_limit > Decimal("0.01"))
    
    # Create budget with limit that will be exceeded
    budget_with_limit = BudgetCreate(
        category=budget_data.category,
        amount_limit=over_budget_limit,
        start_date=budget_data.start_date,
        end_date=budget_data.end_date
    )
    
    created_budget = None
    try:
        created_budget = await budget_service.create_budget(budget_with_limit)
        assert created_budget is not None
        
        # Create expenses that exceed the budget limit
        created_expense_ids = []
        for amount in expense_amounts:
            # Generate a random date within the budget period
            days_range = (budget_data.end_date - budget_data.start_date).days
            if days_range > 0:
                random_days = random.randint(0, days_range)
            else:
                random_days = 0
            expense_date = budget_data.start_date + timedelta(days=random_days)
            
            expense_data = ExpenseCreate(
                date=expense_date,
                amount=amount,
                category=budget_data.category,  # Same category as budget
                account="TestAccount",
                notes="Test expense for over-budget flagging"
            )
            
            created_expense = await expense_service.create_expense(expense_data)
            created_expense_ids.append(created_expense.id)
        
        # Retrieve the budget to get calculated usage
        retrieved_budget = await budget_service.get_budget(created_budget.id)
        
        # Verify the budget is flagged as over-budget
        assert retrieved_budget is not None
        assert retrieved_budget.usage is not None
        
        # Verify that total expenses exceed the limit
        assert total_expenses > over_budget_limit, \
            f"Test setup error: total expenses {total_expenses} should exceed limit {over_budget_limit}"
        
        # Verify the calculated amount matches our total
        assert retrieved_budget.usage.amount_spent == total_expenses, \
            f"Expected amount_spent {total_expenses}, but got {retrieved_budget.usage.amount_spent}"
        
        # Verify is_over_budget flag is True
        assert retrieved_budget.usage.is_over_budget == True, \
            f"Expected is_over_budget=True when expenses ({total_expenses}) exceed limit ({over_budget_limit}), " \
            f"but got is_over_budget={retrieved_budget.usage.is_over_budget}"
        
        # Verify percentage_used exceeds 100%
        assert retrieved_budget.usage.percentage_used > Decimal('100.00'), \
            f"Expected percentage_used > 100%, but got {retrieved_budget.usage.percentage_used}%"
        
        # Verify the percentage calculation is accurate
        expected_percentage = (total_expenses / over_budget_limit) * Decimal('100')
        assert retrieved_budget.usage.percentage_used == expected_percentage, \
            f"Expected percentage {expected_percentage}%, but got {retrieved_budget.usage.percentage_used}%"
        
        # Clean up: delete expenses and budget
        for expense_id in created_expense_ids:
            await expense_service.delete_expense(expense_id)
        await budget_service.delete_budget(created_budget.id)
        
    except ValueError as e:
        # If budget creation fails due to overlap, clean up and skip this iteration
        if "already exists" in str(e) or "overlap" in str(e).lower():
            if created_budget:
                await budget_service.delete_budget(created_budget.id)
            assume(False)  # Skip this test case
        else:
            raise
