from email_assistant.email_scripts.outlook_account.utils_outlook import get_account


# def get_folder(email: str, folder_name: str = "inbox"):
#    account = get_account(email)
#    mailbox = account.mailbox()
#    if folder_name == "inbox":
#        inbox = mailbox.inbox_folder()
#    elif folder_name == "sent":
#        inbox = mailbox.sent_folder()
#    elif folder_name == "drafts":
#        inbox = mailbox.drafts_folder()
#    elif folder_name == "deleted":
#        inbox = mailbox.deleted_items_folder()
#    else:
#        inbox = mailbox.get_folder(folder_name=folder_name)
#    return inbox


def check_access_to_outlook(email_addr: str):
    """
    Check if the email address has access to the outlook account.
    Running this function shouldn't raise error
    """

    account = get_account(email_addr)
    mailbox = account.mailbox()
    try:
        inbox = mailbox.inbox_folder()
        inbox.get_messages(limit=1)
        return True
    except Exception as e:
        print(f"Error checking access to outlook: {e}")
        return False
