from email_assistant.db.operations import insert_from_df, get_df_from_query
import pandas as pd
from email_assistant.utils.email_passwords import decode_string
from email_assistant.email_scripts.imap_account.folders_utils import (
    get_mailbox,
    check_and_create_new_folders,
    get_imap_folder_from_name,
    # move_email_to_folder,
    label_email,
)
from email_assistant.email_scripts.imap_account.create_draft import create_draft_imap
from email_assistant.email_scripts.imap_account.get_emails import (
    read_last_n_last_emails,
    get_emails_body,
)
from typing import Dict, List, Set
import logging

from email_assistant.ai.utils import classify_email, create_ai_draft_response

from datetime import datetime, timedelta
import imaplib
from email.utils import parsedate_to_datetime
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_ids_not_in_table(smtp_msg_ids):
    query = f"""
    WITH candidate_ids (smtp_msg_id) AS (
        VALUES {', '.join(f"('{i}')" for i in smtp_msg_ids)}
    )
    SELECT candidate_ids.smtp_msg_id
    FROM candidate_ids
    LEFT JOIN received_emails ON received_emails.smtp_msg_id = candidate_ids.smtp_msg_id
    WHERE received_emails.smtp_msg_id IS NULL;
    """
    df = get_df_from_query(query)
    return df.smtp_msg_id.to_list()


def get_email_infos(email_account):
    query = f"""select * from email_accounts where email = '{email_account}'"""
    email_infos = get_df_from_query(query)
    if len(email_infos) == 0:
        raise ValueError(f"Email account {email_account} not found in database")
    else:
        email_infos = email_infos.iloc[0]
        email_infos = email_infos.to_dict()
        email_infos["imap_pwd"] = decode_string(email_infos["imap_pwd"])
        return email_infos


def get_emails_with_drafts_or_answers(mailbox, smtp_msg_ids: List[str]) -> Set[str]:
    """
    Efficiently check which emails in a list already have drafts or have been answered.

    Args:
        mailbox: An authenticated IMAP4_SSL connection
        smtp_msg_ids: List of SMTP message IDs to check

    Returns:
        Set of SMTP message IDs that already have drafts or have been answered
    """
    if not smtp_msg_ids:
        return set()

    emails_with_drafts_or_answers = set()

    try:
        # First check drafts folder
        folder_list_data = mailbox.list()[1]
        draft_folder = get_imap_folder_from_name(folder_list_data, "draft")

        if draft_folder:
            status, _ = mailbox.select(draft_folder)
            if status != "OK":
                logger.error(f"Failed to select draft folder: {draft_folder}")
                return emails_with_drafts_or_answers

            # For each message ID, check separately for References and In-Reply-To
            for msg_id in smtp_msg_ids:
                # Try searching for References header
                try:
                    status, data = mailbox.search(None, f'HEADER References "{msg_id}"')
                    if status == "OK" and data[0]:
                        emails_with_drafts_or_answers.add(msg_id)
                        logger.info(
                            f"Found existing draft with References for message ID: {msg_id}"
                        )
                        continue  # Skip to next message ID if we found a match
                except Exception as e:
                    logger.warning(f"Error searching References header: {e}")

                # Try searching for In-Reply-To header
                try:
                    status, data = mailbox.search(
                        None, f'HEADER In-Reply-To "{msg_id}"'
                    )
                    if status == "OK" and data[0]:
                        emails_with_drafts_or_answers.add(msg_id)
                        logger.info(
                            f"Found existing draft with In-Reply-To for message ID: {msg_id}"
                        )
                except Exception as e:
                    logger.warning(f"Error searching In-Reply-To header: {e}")

        # Check sent folder for replies
        emails_with_drafts_or_answers = check_sent_folder_for_replies(
            mailbox, folder_list_data, smtp_msg_ids, emails_with_drafts_or_answers
        )
        # Check inbox for more recent messages in the same thread
        emails_with_drafts_or_answers = check_inbox_for_thread_replies(
            mailbox, folder_list_data, smtp_msg_ids, emails_with_drafts_or_answers
        )

        return emails_with_drafts_or_answers

    except Exception as e:
        logger.exception(f"Error checking for existing drafts: {e}")
        return emails_with_drafts_or_answers


def check_sent_folder_for_replies(
    mailbox: imaplib.IMAP4_SSL,
    folder_list_data,
    smtp_msg_ids,
    emails_with_drafts_or_answers,
):
    """
    Check the sent folder for replies to the given message IDs.

    Args:
        mailbox: An authenticated IMAP4_SSL connection
        folder_list_data: List of folders in the mailbox
        smtp_msg_ids: List of SMTP message IDs to check
        emails_with_drafts_or_answers: Set of message IDs that already have drafts

    Returns:
        Updated set of message IDs that have drafts or have been answered
    """
    sent_folder = get_imap_folder_from_name(folder_list_data, "sent")
    if sent_folder:
        status, _ = mailbox.select(sent_folder)
        if status != "OK":
            logger.error(f"Failed to select sent folder: {sent_folder}")
            return emails_with_drafts_or_answers

        # For each message ID not already found in drafts, check sent folder
        for msg_id in [
            id for id in smtp_msg_ids if id not in emails_with_drafts_or_answers
        ]:
            # Try searching for References header
            try:
                status, data = mailbox.search(None, f'HEADER References "{msg_id}"')
                if status == "OK" and data[0]:
                    emails_with_drafts_or_answers.add(msg_id)
                    logger.info(
                        f"Found sent reply with References for message ID: {msg_id}"
                    )
                    continue  # Skip to next message ID if we found a match
            except Exception as e:
                logger.warning(f"Error searching References header: {e}")

            # Try searching for In-Reply-To header
            try:
                status, data = mailbox.search(None, f'HEADER In-Reply-To "{msg_id}"')
                if status == "OK" and data[0]:
                    emails_with_drafts_or_answers.add(msg_id)
                    logger.info(
                        f"Found sent reply with In-Reply-To for message ID: {msg_id}"
                    )
            except Exception as e:
                logger.warning(f"Error searching In-Reply-To header: {e}")

    return emails_with_drafts_or_answers


def check_inbox_for_thread_replies(
    mailbox: imaplib.IMAP4_SSL,
    folder_list_data,
    smtp_msg_ids: List[str],
    emails_with_drafts_or_answers: Set[str],
) -> Set[str]:
    """
    Check the inbox for more recent messages in the same thread.

    Args:
        mailbox: An authenticated IMAP4_SSL connection
        folder_list_data: List of folders in the mailbox
        smtp_msg_ids: List of SMTP message IDs to check
        emails_with_drafts_or_answers: Set of message IDs that already have drafts/answers

    Returns:
        Updated set of message IDs that have drafts or have been answered
    """
    inbox_folder = get_imap_folder_from_name(folder_list_data, "inbox")
    if not inbox_folder:
        return emails_with_drafts_or_answers

    status, _ = mailbox.select(inbox_folder)
    if status != "OK":
        logger.error(f"Failed to select inbox folder: {inbox_folder}")
        return emails_with_drafts_or_answers

    # For each message ID not already found in drafts or sent, check inbox
    for msg_id in [
        id for id in smtp_msg_ids if id not in emails_with_drafts_or_answers
    ]:
        try:
            # First, get the date of the original message
            status, data = mailbox.search(None, f'HEADER Message-ID "{msg_id}"')
            if status != "OK" or not data[0]:
                # If we can't find the original message, try to find it by subject
                continue

            original_msg_uid = data[0].split()[0]
            status, msg_data = mailbox.fetch(
                original_msg_uid, "(BODY.PEEK[HEADER.FIELDS (DATE SUBJECT)])"
            )
            if status != "OK":
                continue

            # Extract date and subject from original message
            original_date = None
            original_subject = None

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    header_data = response_part[1].decode("utf-8")
                    for line in header_data.splitlines():
                        if line.startswith("Date:"):
                            date_str = line.split(":", 1)[1].strip()
                            try:
                                original_date = parsedate_to_datetime(date_str)
                            except ValueError:
                                # If we can't parse the date, skip this message
                                continue
                        elif line.startswith("Subject:"):
                            original_subject = line.split(":", 1)[1].strip()

            if not original_date or not original_subject:
                continue

            # Now search for messages with the same or similar subject (RE: or FWD: prefixes)
            clean_subject = re.sub(
                r"^(?:RE|FWD|FW):\s*", "", original_subject, flags=re.IGNORECASE
            )
            search_subject = f'SUBJECT "{clean_subject}"'

            status, data = mailbox.search(None, search_subject)
            if status != "OK" or not data[0]:
                continue

            thread_msg_uids = data[0].split()

            # Check each message in the thread
            for uid in thread_msg_uids:
                if uid == original_msg_uid:
                    continue  # Skip the original message

                # Get the date of this message
                status, msg_data = mailbox.fetch(
                    uid, "(BODY.PEEK[HEADER.FIELDS (DATE REFERENCES IN-REPLY-TO)])"
                )
                if status != "OK":
                    continue

                # Check if this message is in the same thread and is newer
                is_in_thread = False
                thread_date = None

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        header_data = response_part[1].decode("utf-8")

                        # Check if it's in the same thread
                        if msg_id in header_data:
                            is_in_thread = True

                        # Get the date
                        for line in header_data.splitlines():
                            if line.startswith("Date:"):
                                date_str = line.split(":", 1)[1].strip()
                                try:
                                    thread_date = parsedate_to_datetime(date_str)
                                except ValueError:
                                    continue

                # If this message is in the same thread and is newer, mark as answered
                if is_in_thread and thread_date and thread_date > original_date:
                    emails_with_drafts_or_answers.add(msg_id)
                    logger.info(
                        f"Found more recent message in the same thread for: {msg_id}"
                    )
                    break

        except Exception as e:
            logger.warning(f"Error checking inbox for thread replies: {e}")
            continue

    return emails_with_drafts_or_answers


def main(email_infos: Dict):

    imap_server = email_infos.get("imap_server", "smtp.gmail.com")
    imap_port = email_infos.get("imap_port", 993)
    imap_login = email_infos.get("imap_login")
    imap_pwd = email_infos.get("imap_pwd")

    mailbox = get_mailbox(
        imap_server,
        imap_port,
        imap_login,
        imap_pwd,
    )
    if mailbox is None:
        return

    folder_list_data = check_and_create_new_folders(mailbox)

    inbox_folder = get_imap_folder_from_name(folder_list_data, "inbox")
    (
        all_received_email_list,
        all_email_ids,
        all_names_list,
        subject_list,
        all_dates,
        smtp_ids,
        receiver_emails,
    ) = read_last_n_last_emails(
        imap_server,
        imap_port,
        imap_login,
        imap_pwd,
        n_last=10,
        mailbox_folder=inbox_folder,
        cutoff_date=(datetime.today() - timedelta(days=1)).strftime("%d-%b-%Y"),
    )
    emails_data = pd.DataFrame(
        {
            "Email ID": all_email_ids,
            "sender": all_names_list,
            "Subject": subject_list,
            "Date": all_dates,
            "smtp_msg_id": smtp_ids,
            "email_account": imap_login,
            "Received Email": all_received_email_list,
        }
    )
    emails_data = emails_data[
        emails_data["Received Email"] != emails_data["email_account"]
    ]
    if len(emails_data) == 0:
        return
    ids_not_in_table = check_ids_not_in_table(smtp_ids)
    emails_data = emails_data[emails_data["smtp_msg_id"].isin(ids_not_in_table)]
    # fetch bodies for these emails:
    all_bodies, all_dates = get_emails_body(mailbox, emails_data["Email ID"].to_list())

    emails_data["body"] = all_bodies
    emails_data = emails_data.iloc[::-1].reset_index(drop=True)
    if len(emails_data) == 0:
        return

    # Get all emails that need to be processed
    to_respond_emails = []
    for _, row in emails_data.iterrows():
        new_folder = classify_email(row["Subject"] + "\n" + row.body)["label"]
        new_folder = new_folder if " " not in new_folder else '"' + new_folder + '"'
        # move_email_to_folder(mailbox, "inbox", new_folder, [row["Email ID"]])
        label_email(mailbox, "inbox", new_folder, [row["Email ID"]])

        # Add to list of emails that need responses
        if "To respond" in new_folder:
            to_respond_emails.append(row)

    # If we have emails that need responses, check which ones already have drafts/answers
    if to_respond_emails:
        draft_folder = get_imap_folder_from_name(folder_list_data, "draft")
        smtp_ids_to_check = [row["smtp_msg_id"] for row in to_respond_emails]

        # Efficiently get all emails that already have drafts or answers
        emails_with_drafts_or_answers = get_emails_with_drafts_or_answers(
            mailbox, smtp_ids_to_check
        )

        # Create drafts only for emails that don't already have drafts or answers
        for row in to_respond_emails:
            if row["smtp_msg_id"] not in emails_with_drafts_or_answers:
                draft_body = create_ai_draft_response(
                    row.body, row.sender, row.email_account, row.Subject
                )
                create_draft_imap(
                    mailbox,
                    imap_login,
                    row["Subject"],
                    draft_body,
                    row["sender"],
                    row["smtp_msg_id"],
                    draft_folder=draft_folder,
                )
            else:
                logger.info(
                    f"Skipping draft creation for already answered/drafted email: {row['smtp_msg_id']}"
                )

    mailbox.logout()

    df_to_insert = emails_data[["sender", "email_account", "smtp_msg_id"]]
    df_to_insert.loc[:, ["email_classified"]] = True

    df_to_insert = df_to_insert.drop_duplicates(subset="smtp_msg_id").reset_index(
        drop=True
    )
    insert_from_df(df_to_insert, "received_emails")
