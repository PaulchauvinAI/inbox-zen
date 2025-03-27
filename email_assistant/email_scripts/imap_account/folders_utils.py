import imaplib
import re
from email_assistant.config import FOLDERS
from email_assistant.db.utils import execute_query


def get_mailbox(imap_server, imap_port, imap_login, imap_password):
    try:
        mailbox = imaplib.IMAP4_SSL(imap_server, int(imap_port))
        mailbox.login(imap_login, imap_password.replace(" ", ""))
        return mailbox
    except (imaplib.IMAP4.error, ConnectionRefusedError) as e:
        print(e)
        if any(
            msg in e.args[0].decode() if isinstance(e.args[0], bytes) else e.args[0]
            for msg in ("[AUTH] Authentication failed.", "Invalid credentials")
        ):
            error_text = str(e)
            # disconnect in database:
            query = f"""UPDATE email_accounts 
                SET disconnected = TRUE, last_error = '{error_text}'
                WHERE imap_login = '{imap_login}';"""
            execute_query(query)
        return None


def list_folders(folder_list_data):
    """list available folders"""
    folders = []
    for folder in folder_list_data:
        decoded_folder = folder.decode()
        pattern = r' "\|" | "\." | "\/" '
        decoded_folder_split = re.split(pattern, decoded_folder)
        if len(decoded_folder_split) < 2:
            continue
        folders.append(decoded_folder_split[1])
    return folders, False, ""


def get_imap_folder_from_name(folder_list_data, folder_type):
    """get folder name based on folder type; folder type can be sent, inbox or all"""
    imap_folder = None
    for folder in folder_list_data:
        decoded_folder = folder.decode()
        pattern = r' "\|" | "\." | "\/" '

        # Split the string using the corrected pattern
        decoded_folder_split = re.split(pattern, decoded_folder)
        if len(decoded_folder_split) < 2:
            continue
        if folder_type in decoded_folder.lower():
            imap_folder = decoded_folder_split[1]
        # folders.append(decoded_folder_split[1])
    return imap_folder


def get_imap_separator(mailbox):
    """
    Retrieves the folder hierarchy separator used by the IMAP server.

    :param mailbox: An authenticated imaplib.IMAP4_SSL instance
    :return: The separator character (e.g., '/', '.', etc.) or None if not found
    """
    result, data = mailbox.list()
    if result == "OK" and data:
        # The separator is typically the second element in the response string
        first_entry = data[0].decode()  # Decode bytes to string
        parts = first_entry.split(" ")
        if len(parts) > 2:
            return parts[1].strip('"')  # Extract separator
    return None  # Return None if not found


def create_folder(mailbox, folder_name):
    try:
        folder_name = f'"{folder_name}"'
        result, data = mailbox.create(folder_name)
        if result == "OK":
            created_folder = folder_name
        else:
            print("Failed to create folder")
            created_folder = None
        # mailbox.logout()
        return created_folder
    except Exception as e:
        print(f"Error creating folder {folder_name}: {e}")
        return None


def move_email_to_folder(mailbox, old_folder_name, new_folder_name, email_ids):
    mailbox.select(old_folder_name)
    # Ensure email_ids are sorted from newest to oldest (optional)
    for email_id in email_ids:
        try:
            # Copy the email to the new folder
            email_id = str(email_id).encode("utf-8")
            mailbox.copy(email_id, new_folder_name)

            # Mark the email as deleted in the old folder
            mailbox.store(email_id, "+FLAGS", "\\Deleted")
        except imaplib.IMAP4.error as e:
            print(f"Error processing email ID {email_id}: {e}")

    # Expunge once after all emails are processed
    mailbox.expunge()


def label_email(mailbox, source_folder_name, label_folder_name, email_ids):
    """
    Adds a label to emails by copying them to another folder without removing them from the source folder.

    IMPORTANT: The behavior of this function depends on the email server implementation:
    - For Gmail (which uses labels), this will make the email appear in both folders
    - For traditional IMAP servers, this will create a duplicate of the email in the second folder
      (the same email will exist in two places with two different message IDs)
    - Some IMAP servers may not support this operation at all

    Args:
        mailbox: An authenticated IMAP mailbox object
        source_folder_name: The folder where the emails currently exist
        label_folder_name: The folder/label to add to these emails
        email_ids: List of email IDs to label

    Returns:
        bool: True if the operation was successful, False otherwise
    """
    try:
        mailbox.select(source_folder_name)
        success = True

        for email_id in email_ids:
            try:
                # Convert email_id to bytes if it's not already
                email_id = str(email_id).encode("utf-8")

                # Copy the email to the label folder without deleting from source
                result = mailbox.copy(email_id, label_folder_name)

                if result[0] != "OK":
                    print(f"Failed to apply label to email ID {email_id}: {result}")
                    success = False

            except imaplib.IMAP4.error as e:
                print(f"Error labeling email ID {email_id}: {e}")
                success = False

        return success
    except Exception as e:
        print(f"Error in label_email function: {e}")
        return False


def check_and_create_new_folders(mailbox, folder_list=FOLDERS):
    """check if the folders exist; if not create them"""
    result, data = mailbox.list()
    if result == "OK":
        existing_folders = []
        for folder in data:
            decoded_folder = folder.decode()
            pattern = r' "\|" | "\." | "\/" '
            decoded_folder_split = re.split(pattern, decoded_folder)
            if len(decoded_folder_split) < 2:
                continue
            existing_folders.append(decoded_folder_split[1])
        for folder in folder_list:
            if f'"{folder}"' not in existing_folders and folder not in existing_folders:
                create_folder(mailbox, folder)
        return data
    else:
        return None


"""
def remove_spam_open_and_move(
    imap_server,
    imap_port,
    imap_login,
    imap_password,
    email_ids,
    old_folder_name,
    mailead_folder='"mailead"',
):
    mail = imaplib.IMAP4_SSL(imap_server, int(imap_port))
    mail.login(imap_login, imap_password)
    email_ids.sort()
    email_ids.reverse()  # otherwise when there are more than 2 elements it does not work since the ids change
    for email_id in email_ids:
        try:
            mail.select(old_folder_name)
            mail.store(email_id, "+FLAGS", "\\Seen")
            mail.copy(email_id, mailead_folder)

            mail.select(mailead_folder)

            mail.select(old_folder_name)
            mail.store(email_id, "+FLAGS", "\\Deleted")

            mail.expunge()
        except imaplib.IMAP4.error as e:
            print(f"Error processing email ID {email_id}: {e}")

    mail.logout()
"""


def revert_folders_gmail(email_infos):
    mailbox = get_mailbox(
        email_infos["imap_server"],
        email_infos["imap_port"],
        email_infos["imap_login"],
        email_infos["imap_pwd"],
    )
    if mailbox is None:
        return

    result, folder_list_data = mailbox.list()
    if result != "OK":
        print("Failed to retrieve folder list")
        return

    result, folders_list_data = mailbox.list()
    for folder in FOLDERS:
        folder = get_imap_folder_from_name(folders_list_data, folder.lower())
        if folder is not None:
            mailbox.select(folder)
            result, data = mailbox.search(None, "ALL")
            if result != "OK":
                print(f"Failed to retrieve emails from folder: {folder}")
                continue
            email_ids = data[0].split()
            if email_ids:
                email_ids = [bs.decode("utf-8") for bs in email_ids]
                move_email_to_folder(mailbox, folder, "inbox", email_ids)
            mailbox.delete(folder)
    mailbox.logout()


if __name__ == "__main__":
    # example to get esp_msg_id for gmail smtp
    imap_server = "imap.gmail.com"
    imap_login = "p.homeimagine@gmail.com"
    imap_password = "zwnldrtqnamlxqbs"

    port = 993

    mailbox = get_mailbox(imap_server, port, imap_login, imap_password)

    folder_list_data = check_and_create_new_folders(mailbox)
    mailbox.logout()

    folder = get_imap_folder_from_name(folder_list_data, "inbox")
    print(folder)

    # folders = list_folders(imap_server, port, imap_login, imap_password)

    # all_email_ids, subject_list, smtp_ids = list_emails_from_folder(
    #    imap_server, port, imap_login, imap_password, folder, n_last=10
    # )
    # print(subject_list, smtp_ids)
