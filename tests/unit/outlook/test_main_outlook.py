from email_assistant.email_scripts.update_inbox import main
from dotenv import load_dotenv
import os

load_dotenv()

outlook_account = os.getenv("OUTLOOK_ACCOUNT")


def test_main():
    main(outlook_account)
