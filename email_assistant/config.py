from O365.category import CategoryColor
from dotenv import load_dotenv
import os

load_dotenv()

# Outlook redirect URI: must be the same as the one in the outlook app
REDIRECT_URI_LIVE = "https://inbox-zen.com/confirmation"
REDIRECT_URI_TEST = "http://localhost:5173/confirmation"

# S3 BUCKET to save outlook tokens
BUCKET_NAME = os.getenv("BUCKET_NAME")
FOLDER_NAME = os.getenv("FOLDER_NAME")

FOLDERS = [
    "To respond",
    "Fyi",
    "Comment",
    "Notification",
    "Meeting Update",
    # "Awaiting Reply",
    "Actioned",
    "Marketing",
]


CATEGORY_COLORS = {
    "To respond": CategoryColor.RED,
    "Fyi": CategoryColor.ORANGE,
    "Comment": CategoryColor.YELLOW,
    "Notification": CategoryColor.GREEN,
    "Meeting Update": CategoryColor.BLUE,
    "Actioned": CategoryColor.PURPLE,
    "Marketing": CategoryColor.BROWN,
}


# Maximum length of an email to be processed by the AI for categorization
LIMIT_EMAIL_LENGTH = 1000
