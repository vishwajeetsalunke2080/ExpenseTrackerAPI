"""
Property-based test for bug condition exploration: Application Startup Constraint Violation

**Validates: Requirements 2.1, 2.2, 2.3**

This test verifies that the problematic initialization functions have been removed
as part of the fix for the null user_id constraint violation bug.

EXPECTED OUTCOME: Test PASSES - functions no longer exist, preventing future misuse.
"""
import pytest


@pytest.mark.asyncio
async def test_property_startup_initialization_functions_removed(test_db):
    """
    Property 1: Expected Behavior - Problematic Initialization Functions Removed
    
    Test that the initialization functions that caused IntegrityError have been removed
    from app.database module. This prevents future misuse and ensures the bug cannot recur.
    
    Bug Condition (FIXED): Functions that attempted to create records without user_id no longer exist
    
    Expected Behavior: ImportError when attempting to import the removed functions
    
    **Validates: Requirements 2.1, 2.2, 2.3**
    """
    # Verify that the problematic functions have been removed
    try:
        from app.database import initialize_default_categories
        pytest.fail(
            "initialize_default_categories still exists in app.database - "
            "this function should have been removed as part of the fix"
        )
    except ImportError:
        # Expected - function has been removed
        pass
    
    try:
        from app.database import initialize_default_account_types
        pytest.fail(
            "initialize_default_account_types still exists in app.database - "
            "this function should have been removed as part of the fix"
        )
    except ImportError:
        # Expected - function has been removed
        pass
    
    # If we reach here, both functions have been successfully removed
    # This confirms the fix is in place and prevents future misuse
