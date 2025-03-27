from O365.utils import AWSS3Backend
from O365 import Account
from dotenv import load_dotenv
import os
import boto3
from email_assistant.config import BUCKET_NAME, FOLDER_NAME

# Load the environment variables from .env file
load_dotenv()

CREDS = (os.getenv("OUTLOOK_CREDS_1"), os.getenv("OUTLOOK_CREDS_2"))
SCOPES_EMAILS = ["basic", "message_all", "offline_access", "settings_all"]


def save_text_to_s3(file_path: str, text: str) -> None:
    """
    Save a text file to an S3 bucket.

    Args:
        file_path (str): The S3 file path where the text file will be saved.
        text (str): The text content to be saved in the file.
    """

    s3_client = boto3.client("s3")
    bucket_name, key = file_path.replace("s3://", "").split("/", 1)
    s3_client.put_object(Bucket=bucket_name, Key=key, Body=text)


def delete_outlook_token(email_addr: str):
    s3_client = boto3.client("s3")
    s3_client.delete_object(Bucket=BUCKET_NAME, Key=f"{FOLDER_NAME}/{email_addr}.txt")


def get_email_token_loc(email_addr):
    return AWSS3Backend(
        bucket_name=BUCKET_NAME,
        filename=f"{FOLDER_NAME}/{email_addr}.txt",
    )


def get_account(email_addr: str = None, creds: tuple = CREDS):
    if email_addr is not None:
        token_backend = get_email_token_loc(email_addr)
        account = Account(creds, token_backend=token_backend)
    else:
        account = Account(creds)
    account.con.scopes = account.protocol.get_scopes_for(SCOPES_EMAILS)
    return account
