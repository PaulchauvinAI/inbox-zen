import re
import dateparser
from email.message import Message
import quopri


def remove_img(text):
    return re.sub(r"<img\s+.*?>", "", text, flags=re.IGNORECASE)


def get_body(email_message: Message, only_html: bool = False) -> str:
    if email_message.is_multipart():
        body = ""
        previous_body = ""
        # If the message is multipart, iterate over its parts to find the text/plain or text/html part
        for part in email_message.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                continue
                # new_part_to_add = part.get_payload(decode=True).decode(errors="ignore")
                # if previous_body != new_part_to_add and not only_html:
                #    body += new_part_to_add
                #    previous_body = new_part_to_add
            elif content_type == "text/html":
                html_part = quopri.decodestring(part.get_payload(decode=True))
                new_part_to_add = html_part.decode("utf-8", errors="ignore")
                if previous_body != new_part_to_add:
                    body += new_part_to_add
                    previous_body = new_part_to_add
    else:
        # If the message is not multipart, return the payload directly
        content_type = email_message.get_content_type()
        if content_type in ["text/plain", "text/html"]:
            body = email_message.get_payload(decode=True).decode(errors="ignore")
        else:
            body = ""
    body = remove_img(body)
    return body


def get_body_v2(email_message: Message) -> str:
    """Same as get_body() but differently, working less well than get_body() but also to consider"""
    body = ""
    if email_message.is_multipart():
        for part in email_message.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain" or content_type == "text/html":
                try:
                    body = part.get_payload(decode=True).decode("utf-8")
                except Exception as e:
                    print(f"error: {str(e)}")
                    body += part.get_payload()
            break
    else:
        try:
            body = email_message.get_payload(decode=True).decode("utf-8")
        except UnicodeDecodeError:
            # Replace problematic characters with a placeholder
            body = email_message.get_payload(decode=True).decode(
                "utf-8", errors="replace"
            )
        except Exception as e:
            print(f"error: {str(e)}")
    return body


def get_body_v3(email_message: Message) -> str:
    body = ""
    html_body = ""
    if email_message.is_multipart():
        for part in email_message.walk():
            content_type = part.get_content_type()
            if content_type == "text/html":
                html_body = part.get_payload(decode=True).decode(errors="ignore")
            elif content_type == "text/plain":
                body = part.get_payload(decode=True).decode(errors="ignore")
    else:
        content_type = email_message.get_content_type()
        if content_type == "text/html":
            html_body = email_message.get_payload(decode=True).decode(errors="ignore")
        elif content_type == "text/plain":
            body = email_message.get_payload(decode=True).decode(errors="ignore")
    return html_body if html_body else body


def extract_emails_from_text(text):
    pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    emails = re.findall(pattern, text)
    return list(set(emails))


def get_date_from_string(date_string):
    # Regular expression pattern to match the date string
    date_pattern = r"(\d+)\s+(\w+)\s+(\d+)\s+(\d+):(\d+)"

    match = re.search(date_pattern, date_string)
    if match:
        day, month_name, year, hour, minute = match.groups()
        date_string = match.group()
        date_obj = dateparser.parse(
            date_string,
            languages=[
                "fr",
                "en",
                "es",
                "de",
                "it",
                "pt",
                "nl",
                "ru",
                "zh",
                "ja",
                "ko",
                "ar",
                "he",
                "hi",
                "sv",
                "da",
                "fi",
                "el",
                "tr",
                "pl",
                "cs",
                "sk",
            ],
        )
        return date_obj
