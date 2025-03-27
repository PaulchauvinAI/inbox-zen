# code to create a new draft message in same thread
import imaplib
from email.mime.text import MIMEText
import time
import logging
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_draft_imap(
    mailbox: imaplib.IMAP4_SSL,
    email_address: str,
    subject: str,
    body: str,
    recipient: str,
    thread_id: Optional[str] = None,
    draft_folder: str = "[Gmail]/Drafts",
) -> bool:
    """
    Create a draft email message in the specified IMAP mailbox.

    Args:
        mailbox: An authenticated IMAP4_SSL connection
        email_address: The sender's email address
        subject: The email subject
        body: The email body content
        recipient: The recipient's email address
        thread_id: Optional Message-ID to link this draft to an existing thread
        draft_folder: The folder where drafts are stored (default: "[Gmail]/Drafts")

    Returns:
        bool: True if draft was successfully created, False otherwise
    """
    try:
        # Create the email message
        msg = MIMEText(body)
        msg["From"] = email_address
        msg["To"] = recipient
        msg["Subject"] = subject

        if thread_id:
            msg["In-Reply-To"] = thread_id  # Link to the thread
            msg["References"] = thread_id  # Helps email clients group it in a thread

        # Select the drafts folder
        status, _ = mailbox.select(draft_folder)
        if status != "OK":
            logger.error(f"Failed to select draft folder: {draft_folder}")
            return False

        # Convert email to raw format
        raw_msg = msg.as_bytes()

        # Append email to the Drafts folder
        timestamp = imaplib.Time2Internaldate(time.time())  # Get the current time
        status, data = mailbox.append(draft_folder, None, timestamp, raw_msg)

        if status != "OK":
            logger.error(f"Failed to create draft: {data}")
            return False

        logger.info(f"Successfully created draft email to {recipient}")
        return True

    except Exception as e:
        logger.exception(f"Error creating draft email: {e}")
        return False
