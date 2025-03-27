from email_assistant.email_scripts.imap_account.main import (
    get_email_infos,
    main as imap_main,
)
from email_assistant.email_scripts.outlook_account.main_categories import (
    main as main_categories,
)
from pydantic import EmailStr


def main(email_account: EmailStr):
    """
    This function is used to update the inbox of a user.
    It is called by the trigger_update_inbox lambda function.
    """
    email_infos = get_email_infos(email_account)
    if email_infos is None:
        raise ValueError(f"Email account {email_account} not found")
    if email_infos["email_provider"].lower() == "gmail":
        imap_main(email_infos)
    elif email_infos["email_provider"].lower() == "outlook":
        main_categories(email_account)

    else:
        raise ValueError(
            f"Email provider {email_infos['email_provider']} not supported"
        )
