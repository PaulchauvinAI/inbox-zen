import imaplib
from email.header import decode_header
import email
import re
from typing import Optional, Tuple, List
from datetime import datetime

from email_assistant.email_scripts.imap_account.utils import (
    get_date_from_string,
    extract_emails_from_text,
    get_body,
)
from email_assistant.db.utils import get_conn
from bs4 import BeautifulSoup


MATCH_EMAIL_RE = r"ENVELOPE.*?\"(.*?)\".*?\"(.*?)\"\)"


def decode_word(encoded_name):
    decoded_tuples = decode_header(encoded_name.strip('"'))

    if isinstance(decoded_tuples[0][0], str):
        return encoded_name
    return decoded_tuples[0][0].decode(decoded_tuples[0][1] or "utf-8")


def disconnect_imap_email(imap_login, imap_pwd, imap_server, error):

    error = error.replace("'", "")
    if len(error) < 5:
        error = "Your email is currently disconnected. Please try logging into your account and then reconnect it in Mailead to resolve the issue."

    conn = get_conn()
    cursor = conn.cursor()
    update_query = f"""
        UPDATE connected_emails
        SET disconnected = TRUE, last_error = '{error}'
        WHERE imap_login = '{imap_login}' and imap_pwd = '{imap_pwd}' and imap_server = '{imap_server}'
    """

    cursor.execute(update_query)
    conn.commit()
    cursor.close()
    conn.close()
    print(f"email {imap_login} disconnected")


def get_n_last_mails_received(
    imap_server: str,
    imap_port: str,
    imap_login: str,
    imap_password: str,
    n_last: int,
    cutoff_date: Optional[str] = None,
    mailbox_folder: str = "inbox",
) -> Tuple[List[str], List[str]]:
    """
    Search Gmail inbox for the last n emails received and return the raw
    bytes of the envelope data for each email.

    Args:
        receiver_email (str): The email address of the receiver.
        password (str): The password of the receiver.
        n_last (int): Number of last emails to fetch.
        cutoff_date (Optional[str]): Only fetch emails since this date.
            Format: 'DD-MM-YYYY'.

    Returns:
        Tuple[List[str], List[str]]: A tuple of two lists. The first list
        contains the raw bytes of the envelope data for each email. The
        second list contains the message IDs of the fetched emails.
    """
    try:
        mail = imaplib.IMAP4_SSL(imap_server, int(imap_port))
        mail.login(imap_login, imap_password)
        success, _ = mail.select(mailbox_folder)
        if success != "OK":
            print("folder does not exist")
            return [], []
    except Exception as e:
        if "Authentication failed." in str(e):
            disconnect_imap_email(
                imap_login, imap_password, imap_server, "wrong imap credentials"
            )
        print(str(e))
        return [], []

    if cutoff_date is None:
        status, messages = mail.search(None, "ALL")
    else:
        date_search = f'(SINCE "{cutoff_date}")'
        status, messages = mail.search(None, date_search)
    messages = messages[0].split()
    # Only consider the last N emails if there are more than N
    start_index = max(0, len(messages) - n_last)
    emails_to_fetch = messages[start_index:]

    # Convert message IDs to strings

    emails_to_fetch_str = [str(msg_id, "utf-8") for msg_id in emails_to_fetch]
    if len(emails_to_fetch_str) == 0:
        print("empty folder")
        return [], []

    # Fetch envelope data for the required emails
    _, envelope_data = mail.fetch(",".join(emails_to_fetch_str), "(ENVELOPE)")
    email_bytes = []
    previous_object = None
    for byte_object in envelope_data:
        if isinstance(byte_object, tuple):
            if len(byte_object) == 2:
                previous_object = (
                    byte_object[0] + byte_object[1]
                )  # should I just remove?
            # previous_object = byte_object
            continue
        if previous_object is not None:
            byte_object = previous_object + byte_object
        previous_object = None
        byte_string = byte_object.decode(errors="ignore")

        email_bytes.append(byte_string)
    mail.logout()
    return email_bytes, emails_to_fetch_str


def extract_sender_email(message):
    # Use regular expression to extract the sender email address
    match = re.search(MATCH_EMAIL_RE, message)
    if match:
        email = "@".join(match.group(2).split("NIL")[-1].split()).replace(
            '"', ""
        )  # Group 2 corresponds to the sender email
        name = match.group(2).split("NIL")[0].split("((")[-1].strip()
        # get subject
        subject = match.group(2).split('" ((')[0]
        subject_match = re.search(r'ENVELOPE \(".+?" "(.+?)"', message)
        subject = subject_match.group(1) if subject_match else None

        name = decode_word(name).strip('"')
        if subject is not None:
            subject = decode_word(subject)
        else:
            subject = ""

        date_str = match.group(1)
        # msg_id = message.split("NIL NIL NIL ")[-1].strip("))").replace('"', "")
        msg_id_match = re.search(r"<([^<>]+)>", message)
        msg_id = "<" + msg_id_match.group(1) + ">" if msg_id_match else None
        return email, name, subject, date_str, msg_id
    else:
        return None, None, None, None, None


def decode_utf8_subject(subject):
    if "=?" in subject and "?=" in subject:
        try:
            decoded_parts = []
            for part, encoding in decode_header(subject):
                if isinstance(part, bytes):
                    decoded_parts.append(
                        part.decode(encoding or "utf-8", errors="replace")
                    )
                else:
                    decoded_parts.append(part)
            return " ".join(decoded_parts)
        except Exception as e:
            print(f"Error decoding subject: {e}")
            return subject
    return subject


def extract_subjects(email_list):
    subjects = []
    for email_ in email_list:
        # Extract the entire ENVELOPE content
        envelope_match = re.search(r"ENVELOPE\s*\((.+?)\)(?=\s*\))", email_, re.DOTALL)

        if envelope_match:
            envelope_content = envelope_match.group(1)

            # Find all quoted strings and NIL values
            parts = re.findall(r'"([^"]*)"|\bNIL\b', envelope_content)

            # The subject is typically the second non-NIL part
            non_nil_parts = [part for part in parts if part != "NIL"]
            subject = non_nil_parts[1] if len(non_nil_parts) > 1 else "No subject found"
        else:
            subject = "No subject found"

        # Decode UTF-8 encoded subjects
        subject = decode_utf8_subject(subject)

        subjects.append(subject)

    return subjects


# Two functions to extract recipients


def extract_receiver_email(message):
    receiver_match = re.search(r'\(\(NIL NIL "([^"]+)" "([^"]+)"\)', message)
    if receiver_match:
        receiver_email = f"{receiver_match.group(1)}@{receiver_match.group(2)}"
    else:
        receiver_email = None
    return receiver_email


def extract_recipient_email(message):
    email_pattern = re.compile(
        r'\((?:"[^"]+"|NIL) (?:NIL )?"?([^"@() ]+)"? "([^"@() ]+)"\)'
    )
    emails = email_pattern.findall(message)

    if len(emails) >= 4:
        username, domain = emails[3]
        recipient_email = f"{username}@{domain}"
        return recipient_email
    else:
        return None


# main function to get emails from imap server and a given folder
def read_last_n_last_emails(
    imap_server: str,
    imap_port: str,
    imap_login: str,
    imap_password: str,
    n_last: int = 100,
    cutoff_date: Optional[datetime] = None,
    mailbox_folder: str = "inbox",
    extract_receiver: bool = False,
) -> Tuple[List[str], List[str], List[str], List[str]]:
    """Read last n and last emails from Gmail.

    Args:
        receiver_email: The email address to read emails from.
        password: The password of the email address.
        n_last: The number of last emails to read (default: 100).
        cutoff_date: The cutoff date to read emails from (default: None).

    Returns:
        A tuple of four lists: the email addresses, email message IDs,
        sender names, and email subjects.
    """

    email_bytes, all_email_ids = get_n_last_mails_received(
        imap_server,
        imap_port,
        imap_login,
        imap_password,
        n_last,
        cutoff_date=cutoff_date,
        mailbox_folder=mailbox_folder,
    )
    all_received_email_list = []
    all_names_list = []
    subject_list = []
    all_dates = []
    smtp_ids = []
    receiver_email_list = []
    subject_list = extract_subjects(email_bytes)
    for byte_string in email_bytes:
        email, name, subject, date, msg_id = extract_sender_email(byte_string)
        # receiver_email = (
        #    extract_receiver_email(byte_string) if extract_receiver else None
        # )
        receiver_email = (
            extract_recipient_email(byte_string) if extract_receiver else None
        )
        if not isinstance(email, str):
            continue
        all_received_email_list.append(email)
        all_names_list.append(name)
        # subject_list.append(subject)
        all_dates.append(get_date_from_string(date))
        smtp_ids.append(msg_id)
        receiver_email_list.append(receiver_email)
    return (
        all_received_email_list,
        all_email_ids,
        all_names_list,
        subject_list,
        all_dates,
        smtp_ids,
        receiver_email_list,
    )


def get_emails_body(
    mail,
    email_ids=["4693", "4694", "4695"],
    only_html=False,
    folder="inbox",
):
    """Used to get detailed infos on email like send date and body.
    It can take some time to fetch the email bodies."""

    mail.select(folder)

    all_bodies = []
    all_dates = []
    for email_id in email_ids:
        _, msg_data = mail.fetch(email_id, "(BODY.PEEK[])")
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                email_message = email.message_from_bytes(response_part[1])

                all_dates.append(email_message["Date"])

                body = get_body(email_message, only_html)
                # if html, get text to decrease size
                if "html>" in body:
                    soup = BeautifulSoup(body, "html.parser")
                    body = soup.get_text(separator="\n", strip=True)
                all_bodies.append(body)
    return all_bodies, all_dates


def get_all_bounced_emails_gmail(
    imap_server, imap_port, imap_login, imap_pwd, email_list, email_ids, emails_names
):
    """Just check in the last n email received if there is postmaster or delivery
    in email addr and then parse the email to get the email that bounced"""

    ids_bounced = []
    for adress, id, name in zip(email_list, email_ids, emails_names):
        sender_lower = adress.lower() + " " + name.lower()
        # check name first
        if "mail delivery" in sender_lower or "postmaster" in sender_lower:
            ids_bounced.append(id)

    bodies, _ = get_emails_body(
        imap_server, imap_port, imap_login, imap_pwd, email_ids=ids_bounced
    )
    all_bounced_emails = []
    for body in bodies:
        all_bounced_emails += extract_emails_from_text(body)

    all_bounced_emails = [
        ele
        for ele in all_bounced_emails
        if not ele.endswith("@mx.google.com") and not ele.endswith("@mail.gmail.com")
    ]
    return all_bounced_emails
