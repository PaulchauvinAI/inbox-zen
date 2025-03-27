# Database Unit Tests

This directory contains unit tests for the database module in the email assistant application. These tests verify the functionality of database operations without requiring an actual database connection.

## Testing Approach

- **Mocking**: All database connections, engine initialization, and query executions are mocked to ensure tests can run without a real database.
- **Fixtures**: Common mocks are provided as pytest fixtures in `conftest.py` for reuse across test files.
- **Coverage**: Tests aim to cover both normal operation paths and error handling paths.

## Test Files

- `test_operations.py`: Tests for database operations including connection management, query execution, and CRUD operations.

## Running Tests

To run the database tests specifically:

```bash
pytest tests/unit/db -v
```

## Adding New Tests

When adding new database tests:

1. Use the provided fixtures from `conftest.py` where applicable
2. Mock external dependencies
3. Add test cases for both success and error scenarios
4. Verify all parameters are correctly passed to the underlying functions 