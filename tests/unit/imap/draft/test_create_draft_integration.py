import pytest
from unittest.mock import MagicMock, patch
import imaplib
from email_assistant.email_scripts.imap_account.create_draft import create_draft_imap


@pytest.fixture
def mock_email_infos():
    """Mock email_infos dictionary for testing"""
    return {
        "imap_server": "imap.gmail.com",
        "imap_port": 993,
        "imap_login": "test@example.com",
        "imap_pwd": "password123",
    }


@pytest.fixture
def mock_mailbox():
    """Create a mock IMAP mailbox for testing"""
    mock = MagicMock(spec=imaplib.IMAP4_SSL)
    # Configure the mock to return success for select operation
    mock.select.return_value = ("OK", [b"1"])
    return mock


@patch("email_assistant.email_scripts.imap_account.folders_utils.get_mailbox")
@patch("email_assistant.email_scripts.imap_account.main.get_email_infos")
def test_create_draft_example_usage(
    mock_get_email_infos, mock_get_mailbox, mock_email_infos, mock_mailbox
):
    """Test the example usage from the create_draft.py file"""
    # Set up mocks
    mock_get_email_infos.return_value = mock_email_infos
    mock_get_mailbox.return_value = mock_mailbox

    # Test parameters
    email_account = "test@example.com"
    thread_id = "<test-thread-id@example.com>"
    subject = "Test Subject"
    recipient = "recipient@example.com"
    body = "This is a test draft message"

    # Import the necessary functions
    from email_assistant.email_scripts.imap_account.main import get_email_infos
    from email_assistant.email_scripts.imap_account.folders_utils import get_mailbox

    # Get the email info and mailbox
    email_infos = get_email_infos(email_account)
    email_address = email_infos["imap_login"]

    mailbox = get_mailbox(
        email_infos["imap_server"],
        email_infos["imap_port"],
        email_address,
        email_infos["imap_pwd"],
    )

    # Create the draft
    create_draft_imap(
        mailbox,
        email_address,
        subject,
        body,
        recipient,
        thread_id,
    )

    # Verify get_email_infos was called with the correct email account
    mock_get_email_infos.assert_called_once_with(email_account)

    # Verify get_mailbox was called with the correct parameters
    mock_get_mailbox.assert_called_once_with(
        mock_email_infos["imap_server"],
        mock_email_infos["imap_port"],
        mock_email_infos["imap_login"],
        mock_email_infos["imap_pwd"],
    )

    # Verify mailbox.select was called
    mock_mailbox.select.assert_called_once()

    # Verify mailbox.append was called
    mock_mailbox.append.assert_called_once()

    # Get the arguments passed to append
    args = mock_mailbox.append.call_args[0]

    # Check the email content
    raw_msg = args[3]
    assert f"From: {mock_email_infos['imap_login']}".encode() in raw_msg
    assert f"To: {recipient}".encode() in raw_msg
    assert f"Subject: {subject}".encode() in raw_msg
    assert body.encode() in raw_msg
    assert f"In-Reply-To: {thread_id}".encode() in raw_msg
    assert f"References: {thread_id}".encode() in raw_msg
