import os
from dotenv import load_dotenv

# from email_assistant.email_scripts.revert_inbox import revert_inbox

load_dotenv()

TEST_OUTLOOK_ACCOUNT = os.getenv("TEST_OUTLOOK_ACCOUNT")


# def test_revert_outlook_inbox(account=TEST_OUTLOOK_ACCOUNT):
#    revert_inbox(account, is_test=True)
