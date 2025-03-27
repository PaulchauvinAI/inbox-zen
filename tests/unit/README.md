# Unit Tests for Email Assistant

This directory contains unit tests for the Email Assistant application.

## Tests for `create_draft_imap` Function

The following test files are available for testing the `create_draft_imap` function:

1. `test_create_draft.py` - Basic unit tests for the function
2. `test_create_draft_integration.py` - Integration tests with mocked dependencies
3. `test_create_draft_edge_cases.py` - Tests for edge cases and error handling

## Running the Tests

To run all tests, navigate to the project root directory and run:

```bash
pytest
```

To run a specific test file:

```bash
pytest tests/unit/test_create_draft.py
```

To run tests with more detailed output:

```bash
pytest -v
```

To run tests with coverage report:

```bash
pytest --cov=email_assistant
```

## Test Coverage

The tests cover the following aspects of the `create_draft_imap` function:

- Basic functionality (creating drafts with and without thread IDs)
- Custom draft folders
- Timestamp generation
- Error handling
- Edge cases:
  - Empty body or subject
  - Special characters in the body
  - Unicode characters
  - Multiple recipients
  - Error conditions

## Adding New Tests

When adding new tests, follow these guidelines:

1. Create a new test file if testing a different module or function
2. Use descriptive test function names that explain what is being tested
3. Use pytest fixtures for common setup
4. Use mocks for external dependencies
5. Use simple assert statements to verify behavior 