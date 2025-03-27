"""
Fixtures for database testing
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_db_connection():
    """Mock database connection for tests."""
    with patch("email_assistant.db.operations.get_connection") as mock:
        mock_conn = MagicMock()
        mock_context = MagicMock(__enter__=MagicMock(return_value=mock_conn))
        mock.return_value = mock_context
        yield mock_conn


@pytest.fixture
def mock_execute_query():
    """Mock execute_query function."""
    with patch("email_assistant.db.operations.execute_query") as mock:
        yield mock


@pytest.fixture
def mock_engine():
    """Mock SQLAlchemy engine."""
    with patch("email_assistant.db.operations.get_engine") as mock_get_engine:
        mock_engine = MagicMock()
        mock_connection = MagicMock()
        mock_get_engine.return_value = mock_engine
        mock_engine.connect.return_value = mock_connection
        yield mock_engine, mock_connection
