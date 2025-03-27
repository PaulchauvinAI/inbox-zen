import pytest
from unittest.mock import MagicMock, patch
import imaplib
import logging
from email_assistant.email_scripts.imap_account.create_draft import create_draft_imap


@pytest.fixture
def mock_mailbox():
    """Create a mock IMAP mailbox for testing"""
    mock = MagicMock(spec=imaplib.IMAP4_SSL)
    # Configure the mock to return success for select operation
    mock.select.return_value = ("OK", [b"1"])
    return mock


@pytest.fixture
def test_data():
    """Common test data for all tests"""
    return {
        "email_address": "test@example.com",
        "subject": "Test Subject",
        "body": "This is a test email body.",
        "recipient": "recipient@example.com",
        "thread_id": "<test-thread-id@example.com>",
        "draft_folder": "[Gmail]/Drafts",
    }


def test_create_draft_basic(mock_mailbox, test_data):
    """Test creating a basic draft without thread ID"""
    # Call the function
    create_draft_imap(
        mock_mailbox,
        test_data["email_address"],
        test_data["subject"],
        test_data["body"],
        test_data["recipient"],
    )

    # Verify mailbox.select was called with the correct folder
    mock_mailbox.select.assert_called_once_with(test_data["draft_folder"])

    # Verify mailbox.append was called
    mock_mailbox.append.assert_called_once()

    # Get the arguments passed to append
    args = mock_mailbox.append.call_args[0]

    # Check folder name
    assert args[0] == test_data["draft_folder"]

    # Check the email content
    raw_msg = args[3]
    assert f"From: {test_data['email_address']}".encode() in raw_msg
    assert f"To: {test_data['recipient']}".encode() in raw_msg
    assert f"Subject: {test_data['subject']}".encode() in raw_msg
    assert test_data["body"].encode() in raw_msg

    # Thread ID should not be present
    assert b"In-Reply-To:" not in raw_msg
    assert b"References:" not in raw_msg


def test_create_draft_with_thread_id(mock_mailbox, test_data):
    """Test creating a draft with a thread ID"""
    # Call the function with thread_id
    create_draft_imap(
        mock_mailbox,
        test_data["email_address"],
        test_data["subject"],
        test_data["body"],
        test_data["recipient"],
        test_data["thread_id"],
    )

    # Verify mailbox.append was called
    mock_mailbox.append.assert_called_once()

    # Get the arguments passed to append
    args = mock_mailbox.append.call_args[0]

    # Check the email content
    raw_msg = args[3]

    # Thread ID should be present
    assert f"In-Reply-To: {test_data['thread_id']}".encode() in raw_msg
    assert f"References: {test_data['thread_id']}".encode() in raw_msg


def test_create_draft_custom_folder(mock_mailbox, test_data):
    """Test creating a draft in a custom folder"""
    custom_folder = "Custom/Drafts"

    # Call the function with custom draft folder
    create_draft_imap(
        mock_mailbox,
        test_data["email_address"],
        test_data["subject"],
        test_data["body"],
        test_data["recipient"],
        draft_folder=custom_folder,
    )

    # Verify mailbox.select was called with the custom folder
    mock_mailbox.select.assert_called_once_with(custom_folder)

    # Verify mailbox.append was called with the custom folder
    args = mock_mailbox.append.call_args[0]
    assert args[0] == custom_folder


@patch("imaplib.Time2Internaldate")
def test_timestamp_generation(mock_time2internaldate, mock_mailbox, test_data):
    """Test that the timestamp is generated correctly"""
    mock_timestamp = b"01-Jan-2023 12:00:00 +0000"
    mock_time2internaldate.return_value = mock_timestamp

    # Call the function
    create_draft_imap(
        mock_mailbox,
        test_data["email_address"],
        test_data["subject"],
        test_data["body"],
        test_data["recipient"],
    )

    # Verify Time2Internaldate was called
    mock_time2internaldate.assert_called_once()

    # Verify the timestamp was passed to append
    args = mock_mailbox.append.call_args[0]
    assert args[2] == mock_timestamp


def test_error_handling(mock_mailbox, test_data):
    """Test error handling when mailbox operations fail"""
    # Make mailbox.append raise an exception
    mock_mailbox.append.side_effect = imaplib.IMAP4.error("Failed to append")

    # Call the function and check if it returns False
    result = create_draft_imap(
        mock_mailbox,
        test_data["email_address"],
        test_data["subject"],
        test_data["body"],
        test_data["recipient"],
    )

    # Verify the function returned False
    assert result is False

    # Verify mailbox.append was called
    mock_mailbox.append.assert_called_once()


def test_select_folder_failure(mock_mailbox, test_data):
    """Test handling of select folder failure (status not OK)"""
    # Configure the mock to return failure for select operation
    mock_mailbox.select.return_value = ("NO", ["Folder doesn't exist"])

    # Call the function
    result = create_draft_imap(
        mock_mailbox,
        test_data["email_address"],
        test_data["subject"],
        test_data["body"],
        test_data["recipient"],
    )

    # Verify the function returned False
    assert result is False

    # Verify mailbox.select was called
    mock_mailbox.select.assert_called_once_with(test_data["draft_folder"])

    # Verify mailbox.append was not called
    mock_mailbox.append.assert_not_called()


def test_append_failure(mock_mailbox, test_data):
    """Test handling of append failure (status not OK)"""
    # Configure the mock to return failure for append operation
    mock_mailbox.append.return_value = ("NO", ["Quota exceeded"])

    # Call the function
    result = create_draft_imap(
        mock_mailbox,
        test_data["email_address"],
        test_data["subject"],
        test_data["body"],
        test_data["recipient"],
    )

    # Verify the function returned False
    assert result is False

    # Verify mailbox.select was called
    mock_mailbox.select.assert_called_once_with(test_data["draft_folder"])

    # Verify mailbox.append was called
    mock_mailbox.append.assert_called_once()


def test_successful_draft_creation_logs_message(mock_mailbox, test_data, caplog):
    """Test that a success message is logged when the draft is created successfully"""
    # Set the log level to capture INFO messages
    caplog.set_level(logging.INFO)

    # Configure the mock to return success for append operation
    mock_mailbox.append.return_value = ("OK", [b"[APPENDUID 1 123]"])

    # Call the function
    result = create_draft_imap(
        mock_mailbox,
        test_data["email_address"],
        test_data["subject"],
        test_data["body"],
        test_data["recipient"],
    )

    # Verify the function returned True
    assert result is True

    # Verify the success message was logged
    assert (
        f"Successfully created draft email to {test_data['recipient']}" in caplog.text
    )
