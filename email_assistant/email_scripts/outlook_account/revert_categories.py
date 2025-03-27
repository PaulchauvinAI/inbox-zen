"""
When a user wants to revert the categorization system, we want to:
1) Remove all categories created by the system from messages
2) Delete the categories from the account
"""

import logging
from pydantic import EmailStr

from email_assistant.email_scripts.outlook_account.utils_outlook import get_account
from email_assistant.email_scripts.outlook_account.main_categories import (
    CATEGORY_COLORS,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def remove_categories_from_messages(mailbox, account, category_names):
    """
    Remove specified categories from all messages in the inbox.

    Args:
        mailbox: The mailbox object
        account: The account object
        category_names: List of category names to remove
    """
    # Get all messages from the inbox
    inbox = mailbox.inbox_folder()
    messages = list(inbox.get_messages(limit=1000))

    logger.info(f"Found {len(messages)} messages in inbox")

    # Get categories for reference
    try:
        outlook_categories = account.outlook_categories()
        categories = outlook_categories.get_categories()
        logger.info(f"Found {len(categories)} categories in account")
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        return

    # Remove categories from messages
    for msg in messages:
        try:
            # Check if message has any of our categories
            msg_categories = msg.categories
            if not msg_categories:
                continue

            changed = False
            # Create a new list without our categories
            new_categories = [
                cat for cat in msg_categories if cat not in category_names
            ]

            # If categories changed, update the message
            if len(new_categories) != len(msg_categories):
                msg.categories = new_categories
                msg.save_message()
                changed = True

            if changed:
                logger.info(f"Removed categories from message: {msg.subject}")
        except Exception as e:
            logger.warning(f"Error removing categories from message {msg.subject}: {e}")


def delete_categories(account, category_names):
    """
    Delete specified categories from the account.

    Args:
        account: The account object
        category_names: List of category names to delete
    """
    try:
        outlook_categories = account.outlook_categories()
        categories = outlook_categories.get_categories()

        for category in categories:
            if category.name in category_names:
                try:
                    category.delete()
                    logger.info(f"Deleted category: {category.name}")
                except Exception as e:
                    logger.warning(f"Error deleting category {category.name}: {e}")
    except Exception as e:
        logger.error(f"Error accessing categories: {e}")


def revert_categories(email_account: EmailStr):
    """
    Revert the categorization system for an email account.

    Args:
        email_account: The email account to revert
    """

    logger.info(f"Reverting categories for {email_account}")

    # Get the account and mailbox
    account = get_account(email_account)
    mailbox = account.mailbox()

    # Get category names from CATEGORY_COLORS
    category_names = list(CATEGORY_COLORS.keys())

    # First remove categories from all messages
    remove_categories_from_messages(mailbox, account, category_names)

    # Then delete the categories themselves
    delete_categories(account, category_names)

    logger.info(f"Successfully reverted categories for {email_account}")
