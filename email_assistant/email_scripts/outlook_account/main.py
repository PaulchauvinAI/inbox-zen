from O365.mailbox import MailBox
from O365.message import Message
from datetime import datetime, timedelta
import pandas as pd
import logging
from typing import List, Dict

from email_assistant.config import FOLDERS
from email_assistant.email_scripts.outlook_account.utils_outlook import get_account
from email_assistant.ai.utils import classify_email, create_ai_draft_response
from email_assistant.db.operations import insert_from_df


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_folder(mailbox: MailBox, folder_name: str = "test"):
    folders_list = mailbox.get_folders()
    if f"{folder_name} from resource: me" not in str(folders_list):
        mailbox.create_child_folder(folder_name)
        print(f"folder {folder_name} created")


def delete_folder(mailbox: MailBox, folder_name: str):
    folder = mailbox.get_folder(folder_name=folder_name)
    # before deleting, move all the messages to the inbox
    smtp_msg_ids = []
    messages = folder.get_messages()
    for msg in messages:
        msg.move(mailbox.inbox_folder())
        smtp_msg_ids.append(msg.internet_message_id)
    folder.delete()
    print(f"folder {folder_name} deleted")


def open_and_move_to_new_folder(
    email_address: str, messages_to_check: pd.DataFrame, old_folder_type: str, n_last=50
):
    account = get_account(email_address)
    mailbox = account.mailbox()
    if old_folder_type == "spam":
        create_folder(mailbox)
        old_folder = mailbox.junk_folder()
    elif old_folder_type == "inbox":
        old_folder = mailbox.inbox_folder()
    else:
        raise ValueError(f"old inbox {old_folder_type} not implemented")

    new_folder = mailbox.get_folder(folder_name="mailead")
    messages = list(old_folder.get_messages(limit=n_last))
    outlook_msg_ids = []
    msg_internet_ids = []
    thread_ids = []
    warmup_in_old_folder = []
    all_subjects_to_check = messages_to_check.msg_subject.to_list()
    all_subjects_to_check_with_re = ["RE: " + sub for sub in all_subjects_to_check]

    subject_to_index = {sub: i for i, sub in enumerate(all_subjects_to_check)}
    subject_to_index.update(
        {sub: i for i, sub in enumerate(all_subjects_to_check_with_re)}
    )
    for index_msg, subj in enumerate(all_subjects_to_check):
        for msg in messages:
            if subj.strip().split("| mailead")[0] in msg.subject.strip():
                msg.move(new_folder)
                msg.mark_as_read()
                outlook_msg_ids.append(msg.object_id)
                msg_internet_ids.append(msg.internet_message_id)
                thread_ids.append(msg.conversation_id)

                associated_warmup_msg = messages_to_check.iloc[index_msg]
                warmup_in_old_folder.append(associated_warmup_msg)
                break

    return warmup_in_old_folder, msg_internet_ids, outlook_msg_ids, thread_ids


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


def check_if_email_has_draft_or_answered(mailbox, message):
    """
    Check if an email already has a draft or has been answered.

    Args:
        mailbox: The mailbox object
        message: The message object to check

    Returns:
        bool: True if the email has a draft or has been answered, False otherwise
    """
    try:
        msg_id = message.internet_message_id
        # Check drafts folder for drafts referencing this email
        drafts_folder = mailbox.drafts_folder()
        drafts = drafts_folder.get_messages()

        for draft in drafts:
            # Check if this draft is a reply to our message
            if hasattr(draft, "conversation_id") and draft.conversation_id:
                # If the draft is part of the same conversation as our message
                if message.conversation_id == draft.conversation_id:
                    logger.info(f"Found existing draft for message ID: {msg_id}")
                    return True

        # Check sent folder to see if this email has been answered
        sent_folder = mailbox.sent_folder()
        sent_messages = sent_folder.get_messages()

        for sent_msg in sent_messages:
            # Check if this sent message is a reply to our message
            if hasattr(sent_msg, "conversation_id") and sent_msg.conversation_id:
                if message.conversation_id == sent_msg.conversation_id:
                    logger.info(f"Found sent reply for message ID: {msg_id}")
                    return True

        return False

    except Exception as e:
        logger.exception(f"Error checking for existing drafts: {e}")
        return False


def create_draft(msg: Message, draft_body_html: str):
    """Create a draft reply to an email.

    Args:
        mailbox: The mailbox object
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


def create_folders_if_not_there(mailbox: MailBox, folder_list=FOLDERS):
    folders_list = mailbox.get_folders()
    for folder in folder_list:
        if folder not in str(folders_list):
            mailbox.create_child_folder(folder)
            print(f"folder {folder} created")


def main(email: str):
    account = get_account(email)
    mailbox = account.mailbox()
    create_folders_if_not_there(mailbox)

    # get all emails from the inbox received today
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

    for i, msg in enumerate(messages):
        bodies.append(msg.body)
        subjects.append(msg.subject)
        smtp_msg_ids.append(msg.internet_message_id)
        senders.append(msg.sender._address)
        new_folder = classify_email(msg.subject + "\n" + msg.body)["label"]
        folder = mailbox.get_folder(folder_name=new_folder)
        msg.move(folder)

        # Add to list of messages that need responses
        if "To respond" in new_folder:
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
