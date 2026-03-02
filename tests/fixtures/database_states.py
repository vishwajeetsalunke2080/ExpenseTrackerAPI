"""
Hypothesis strategies for generating database states.

This module provides strategies for property-based testing of migration logic.
"""

from hypothesis import strategies as st
from dataclasses import dataclass


@dataclass
class DatabaseStateFixture:
    """Represents a test database state."""
    has_alembic_version: bool
    current_revision: str | None
    application_tables: list[str]


def empty_database_strategy():
    """
    Generate empty database states with no tables.
    
    Returns:
        Strategy that generates DatabaseStateFixture with no tables
    """
    return st.builds(
        DatabaseStateFixture,
        has_alembic_version=st.just(False),
        current_revision=st.just(None),
        application_tables=st.just([])
    )



def partial_state_strategy():
    """
    Generate partial state database with tables but no alembic_version.
    
    Returns:
        Strategy that generates DatabaseStateFixture with tables but no version
    """
    table_names = st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu"), min_codepoint=97, max_codepoint=122),
            min_size=3,
            max_size=20
        ),
        min_size=1,
        max_size=20,
        unique=True
    )
    
    return st.builds(
        DatabaseStateFixture,
        has_alembic_version=st.just(False),
        current_revision=st.just(None),
        application_tables=table_names
    )



def migrated_database_strategy():
    """
    Generate migrated database states with alembic_version at various positions.
    
    Returns:
        Strategy that generates DatabaseStateFixture with version table
    """
    # Generate revision strings (simulating Alembic revision IDs)
    revision_id = st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Nd"), min_codepoint=48, max_codepoint=122),
        min_size=12,
        max_size=12
    )
    
    table_names = st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu"), min_codepoint=97, max_codepoint=122),
            min_size=3,
            max_size=20
        ),
        min_size=0,
        max_size=20,
        unique=True
    )
    
    return st.builds(
        DatabaseStateFixture,
        has_alembic_version=st.just(True),
        current_revision=revision_id,
        application_tables=table_names
    )



def corrupted_version_strategy():
    """
    Generate database states with unknown version values in alembic_version.
    
    Returns:
        Strategy that generates DatabaseStateFixture with corrupted version
    """
    # Generate invalid/unknown revision strings
    unknown_revision = st.text(
        alphabet="!@#$%^&*()_+-=[]{}|;:,.<>?",
        min_size=8,
        max_size=16
    ) | st.just("INVALID_REVISION") | st.just("corrupted_version_123")
    
    table_names = st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu"), min_codepoint=97, max_codepoint=122),
            min_size=3,
            max_size=20
        ),
        min_size=0,
        max_size=20,
        unique=True
    )
    
    return st.builds(
        DatabaseStateFixture,
        has_alembic_version=st.just(True),
        current_revision=unknown_revision,
        application_tables=table_names
    )
