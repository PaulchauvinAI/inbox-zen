from email_assistant.email_scripts.imap_account.main import main
from dotenv import load_dotenv
import os

load_dotenv()

gmail_account = os.getenv("GMAIL_ACCOUNT")


def test_main():
    main(gmail_account)
