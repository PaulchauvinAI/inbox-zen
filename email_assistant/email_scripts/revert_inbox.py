from email_assistant.email_scripts.imap_account.main import get_email_infos
from email_assistant.email_scripts.imap_account.folders_utils import (
    revert_folders_gmail,
)
from email_assistant.db.utils import execute_query
from pydantic import EmailStr
from email_assistant.email_scripts.outlook_account.revert_categories import (
    revert_categories,
)
from email_assistant.email_scripts.outlook_account.utils_outlook import (
    delete_outlook_token,
)


def revert_inbox(email_account: EmailStr, is_test: bool = False):
    """
    This function is used to revert the inbox of a user.
    It is used when a user deletes his email account.
    """
    email_infos = get_email_infos(email_account)
    if email_infos["email_provider"].lower() == "gmail":
        revert_folders_gmail(email_infos)
    elif email_infos["email_provider"].lower() == "outlook":
        # remove categories
        revert_categories(email_account)
        # remove outlook access token from s3
        delete_outlook_token(email_account)

    # Delete all received emails for this account
    query = f"DELETE FROM received_emails WHERE email_account = '{email_account}'"
    execute_query(query)
    if not is_test:
        # Remove the email account from database (this will cascade delete related records)
        query = f"DELETE FROM email_accounts WHERE email = '{email_account}'"
        execute_query(query)
    return
