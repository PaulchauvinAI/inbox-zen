import pytest
from unittest.mock import MagicMock, patch
import imaplib
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
        "draft_folder": "[Gmail]/Drafts",
    }


def test_empty_body(mock_mailbox, test_data):
    """Test creating a draft with an empty body"""
    # Call the function with empty body
    create_draft_imap(
        mock_mailbox,
        test_data["email_address"],
        test_data["subject"],
        "",  # Empty body
        test_data["recipient"],
    )

    # Verify mailbox.append was called
    mock_mailbox.append.assert_called_once()

    # Get the arguments passed to append
    args = mock_mailbox.append.call_args[0]

    # Check the email content
    raw_msg = args[3]
    assert f"From: {test_data['email_address']}".encode() in raw_msg
    assert f"To: {test_data['recipient']}".encode() in raw_msg
    assert f"Subject: {test_data['subject']}".encode() in raw_msg

    # Body should be empty but the email should still be valid
    assert b"\n\n" in raw_msg  # Headers and body separator should exist


def test_empty_subject(mock_mailbox, test_data):
    """Test creating a draft with an empty subject"""
    # Call the function with empty subject
    create_draft_imap(
        mock_mailbox,
        test_data["email_address"],
        "",  # Empty subject
        test_data["body"],
        test_data["recipient"],
    )

    # Verify mailbox.append was called
    mock_mailbox.append.assert_called_once()

    # Get the arguments passed to append
    args = mock_mailbox.append.call_args[0]

    # Check the email content
    raw_msg = args[3]
    assert f"From: {test_data['email_address']}".encode() in raw_msg
    assert f"To: {test_data['recipient']}".encode() in raw_msg
    assert b"Subject: " in raw_msg  # Subject header exists but is empty
    assert test_data["body"].encode() in raw_msg


def test_special_characters_in_body(mock_mailbox, test_data):
    """Test creating a draft with special characters in the body"""
    special_body = (
        "This body has special characters: !@#$%^&*()_+{}|:<>?~`-=[]\\;',./\n\t"
    )

    # Call the function with special characters in body
    create_draft_imap(
        mock_mailbox,
        test_data["email_address"],
        test_data["subject"],
        special_body,
        test_data["recipient"],
    )

    # Verify mailbox.append was called
    mock_mailbox.append.assert_called_once()

    # Get the arguments passed to append
    args = mock_mailbox.append.call_args[0]

    # Check the email content
    raw_msg = args[3]
    assert special_body.encode() in raw_msg


def test_unicode_characters(mock_mailbox, test_data):
    """Test creating a draft with Unicode characters"""
    unicode_subject = "Unicode Subject: 你好, こんにちは, 안녕하세요"
    unicode_body = "Unicode Body: 你好, こんにちは, 안녕하세요, Привет, مرحبا, שלום"

    # Call the function with Unicode characters
    create_draft_imap(
        mock_mailbox,
        test_data["email_address"],
        unicode_subject,
        unicode_body,
        test_data["recipient"],
    )

    # Verify mailbox.append was called
    mock_mailbox.append.assert_called_once()

    # Get the arguments passed to append
    args = mock_mailbox.append.call_args[0]

    # Check the email content
    raw_msg = args[3]

    # The raw message should contain the encoded Unicode characters
    # We don't check for the exact encoding, just that the message was created
    assert b"Subject:" in raw_msg
    assert b"From:" in raw_msg
    assert b"To:" in raw_msg
    assert b"Content-Type: text/plain" in raw_msg


def test_multiple_recipients(mock_mailbox, test_data):
    """Test creating a draft with multiple recipients"""
    multiple_recipients = (
        "recipient1@example.com, recipient2@example.com, recipient3@example.com"
    )

    # Call the function with multiple recipients
    create_draft_imap(
        mock_mailbox,
        test_data["email_address"],
        test_data["subject"],
        test_data["body"],
        multiple_recipients,
    )

    # Verify mailbox.append was called
    mock_mailbox.append.assert_called_once()

    # Get the arguments passed to append
    args = mock_mailbox.append.call_args[0]

    # Check the email content
    raw_msg = args[3]
    assert f"To: {multiple_recipients}".encode() in raw_msg


@patch("imaplib.Time2Internaldate")
def test_time2internaldate_error(mock_time2internaldate, mock_mailbox, test_data):
    """Test handling of Time2Internaldate errors"""
    # Make Time2Internaldate raise an exception
    mock_time2internaldate.side_effect = Exception("Time2Internaldate error")

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

    # Verify Time2Internaldate was called
    mock_time2internaldate.assert_called_once()


def test_select_folder_error(mock_mailbox, test_data):
    """Test handling of select folder errors"""
    # Reset the mock to override the fixture's configuration
    mock_mailbox.select.reset_mock()
    # Make mailbox.select raise an exception
    mock_mailbox.select.side_effect = imaplib.IMAP4.error("Failed to select folder")

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

    # Verify select was called
    mock_mailbox.select.assert_called_once()
