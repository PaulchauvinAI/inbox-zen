"""functions like update or revert inbox take time to run, so we need to run them in a separate lambda function to call asynchronously"""

from email_assistant.email_scripts.update_inbox import main
from email_assistant.email_scripts.revert_inbox import revert_inbox
from email_assistant.db.utils import cleanup_db_resources


def handler(event, context):
    try:
        if event["action"] == "update_inbox":
            main(event["email_account"])
        elif event["action"] == "revert_inbox":
            revert_inbox(event["email_account"])
    finally:
        cleanup_db_resources()
