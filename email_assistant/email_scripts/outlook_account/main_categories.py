from O365.message import Message
from datetime import datetime, timedelta
import pandas as pd
import logging
from typing import List, Dict

from email_assistant.email_scripts.outlook_account.utils_outlook import get_account
from email_assistant.ai.utils import classify_email, create_ai_draft_response
from email_assistant.db.operations import insert_from_df
from email_assistant.config import CATEGORY_COLORS


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_categories_if_not_exist(
    account, category_colors: Dict[str, str] = CATEGORY_COLORS
):
    """
    Create categories with specified colors if they don't already exist.

    Args:
        account: The account object
        category_colors: Dictionary mapping category names to colors
    """
    # Get outlook categories
    outlook_categories = account.outlook_categories()

    # Get existing categories
    categories = outlook_categories.get_categories()
    existing_category_names = [cat.name for cat in categories]

    # Create missing categories
    for category_name, color in category_colors.items():
        if category_name not in existing_category_names:
            outlook_categories.create_category(category_name, color=color)
            logger.info(f"Category '{category_name}' with color '{color}' created")


def get_messages_with_drafts_or_answers(
    mailbox, messages: List[Message]
) -> Dict[str, bool]:
    """
    Efficiently check which messages already have drafts or have been answered.

    Args:
        mailbox: The mailbox object
        messages: List of message objects to check

    Returns:
        Dictionary mapping message IDs to boolean indicating if they have drafts/answers
    """
    if not messages:
        return {}

    # Create a dictionary to track which messages have drafts or answers
    messages_with_drafts_or_answers = {}

    # Create a mapping of conversation IDs to message IDs for quick lookup
    conversation_to_msg = {
        msg.conversation_id: msg.internet_message_id
        for msg in messages
        if hasattr(msg, "conversation_id") and msg.conversation_id
    }

    if not conversation_to_msg:
        return {}

    try:
        # Check drafts folder
        drafts_folder = mailbox.drafts_folder()
        drafts = list(drafts_folder.get_messages())

        # Check which conversations have drafts
        for draft in drafts:
            if (
                hasattr(draft, "conversation_id")
                and draft.conversation_id in conversation_to_msg
            ):
                msg_id = conversation_to_msg[draft.conversation_id]
                messages_with_drafts_or_answers[msg_id] = True
                logger.info(f"Found existing draft for message ID: {msg_id}")

        # Check sent folder for replies
        sent_folder = mailbox.sent_folder()
        sent_messages = list(sent_folder.get_messages())

        # Check which conversations have sent replies
        for sent_msg in sent_messages:
            if (
                hasattr(sent_msg, "conversation_id")
                and sent_msg.conversation_id in conversation_to_msg
            ):
                msg_id = conversation_to_msg[sent_msg.conversation_id]
                if msg_id not in messages_with_drafts_or_answers:
                    messages_with_drafts_or_answers[msg_id] = True
                    logger.info(f"Found sent reply for message ID: {msg_id}")

        return messages_with_drafts_or_answers

    except Exception as e:
        logger.exception(f"Error checking for existing drafts: {e}")
        return messages_with_drafts_or_answers


def create_draft(msg: Message, draft_body_html: str):
    """Create a draft reply to an email.

    Args:
        msg: The original message to reply to
        draft_body_html: HTML content for the draft reply

    Returns:
        The created draft message
    """
    # Create a reply draft
    draft = msg.reply()

    # Set the body content
    draft.body = draft_body_html

    # Save as draft
    draft.save_draft()

    return draft


def main(email: str):
    """
    Main function to process emails using categories instead of folders.

    Args:
        email: The email address to process
    """
    account = get_account(email)
    mailbox = account.mailbox()

    # Create categories if they don't exist
    create_categories_if_not_exist(account)

    # Get all emails from the inbox received today
    inbox = mailbox.inbox_folder()

    # Get today's date at midnight (start of the day)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    # Get tomorrow's date at midnight (end of the day)
    tomorrow = today + timedelta(days=1)

    # Create a query for emails received today
    query = f"receivedDateTime ge {today.isoformat()}Z and receivedDateTime lt {tomorrow.isoformat()}Z"

    # Use the query with get_messages
    messages = list(inbox.get_messages(limit=100, query=query))

    # get the email bodies and subjects
    bodies = []
    subjects = []
    smtp_msg_ids = []
    senders = []

    # Collect messages that need responses
    to_respond_messages = []
    to_respond_indices = []

    # Get outlook categories for reference
    outlook_categories = account.outlook_categories()
    categories_dict = {cat.name: cat for cat in outlook_categories.get_categories()}

    from email_assistant.email_scripts.imap_account.main import check_ids_not_in_table

    all_smtp_msg_ids = [msg.internet_message_id for msg in messages]

    ids_not_in_table = check_ids_not_in_table(all_smtp_msg_ids)
    for i, msg in enumerate(messages):
        if msg.internet_message_id not in ids_not_in_table:
            continue
        bodies.append(msg.body)
        subjects.append(msg.subject)
        smtp_msg_ids.append(msg.internet_message_id)
        senders.append(msg.sender._address)
        # Classify the email
        category_name = classify_email(msg.subject + "\n" + msg.body)["label"]

        # Get the category object
        if category_name in categories_dict:
            category = categories_dict[category_name]

            # Apply the category to the message using the add_category method
            try:
                msg.add_category(category)
                # Save the changes to persist the category
                msg.save_message()
                logger.info(
                    f"Applied category '{category_name}' to message with subject: {msg.subject}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to apply category '{category_name}' to message: {e}"
                )
        else:
            logger.warning(
                f"Category '{category_name}' not found in categories dictionary"
            )

        # Add to list of messages that need responses
        if category_name == "To respond":
            to_respond_messages.append(msg)
            to_respond_indices.append(i)

    # If we have messages that need responses, check which ones already have drafts/answers
    if to_respond_messages:
        # Efficiently get all messages that already have drafts or answers
        messages_with_drafts_or_answers = get_messages_with_drafts_or_answers(
            mailbox, to_respond_messages
        )

        # Create drafts only for messages that don't already have drafts or answers
        for msg in to_respond_messages:
            if msg.internet_message_id not in messages_with_drafts_or_answers:
                draft_body = create_ai_draft_response(
                    msg.body, msg.sender._address, email, msg.subject
                )
                create_draft(msg, draft_body)
            else:
                logger.info(
                    f"Skipping draft creation for already answered/drafted email: {msg.internet_message_id}"
                )

    emails_data = pd.DataFrame(
        {
            "email_account": email,
            "sender": senders,
            "smtp_msg_id": smtp_msg_ids,
        }
    )
    df_to_insert = emails_data[["sender", "email_account", "smtp_msg_id"]]
    df_to_insert.loc[:, ["email_classified"]] = True

    df_to_insert = df_to_insert.drop_duplicates(subset="smtp_msg_id").reset_index(
        drop=True
    )
    insert_from_df(df_to_insert, "received_emails")
