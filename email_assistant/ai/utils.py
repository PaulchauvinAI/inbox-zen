from openai import OpenAI
from dotenv import load_dotenv
import os
import re
import threading
import html
from pydantic import BaseModel
from typing import Literal
from email_assistant.config import FOLDERS
import json
from email_assistant.config import LIMIT_EMAIL_LENGTH

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class EmailLabel(BaseModel):
    label: Literal[tuple(FOLDERS)]


class FunctionTimedOut(Exception):
    pass


def timeout(seconds, function_name=""):
    """
    Decorator that adds a timeout to a function.

    This decorator will run the decorated function in a separate thread and
    raise a FunctionTimedOut exception if the function takes longer than
    the specified timeout to complete.

    Args:
        seconds (int): Maximum execution time in seconds before timing out
        function_name (str, optional): Name of the function for error reporting

    Returns:
        decorator: A decorator function that applies the timeout logic

    Raises:
        FunctionTimedOut: If the function execution exceeds the timeout period
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            result = [None]

            def target():
                result[0] = func(*args, **kwargs)

            thread = threading.Thread(target=target)
            thread.start()
            thread.join(seconds)
            if thread.is_alive():
                raise FunctionTimedOut(f"Function timed out for {function_name}")
            return result[0]

        return wrapper

    return decorator


@timeout(10, "openai api")
def generate_with_ai(
    prompt, api_key=OPENAI_API_KEY, response_format=None, model="gpt-4o-mini"
):
    """
    Generates text using OpenAI's API with a timeout protection.

    This function calls OpenAI's chat API with the provided prompt
    and handles both regular text responses and structured responses
    using the response_format parameter.

    Args:
        prompt (str): The input prompt to send to the AI model
        api_key (str, optional): OpenAI API key. Defaults to environment variable.
        response_format (dict, optional): Format specification for structured responses.
                                         None for unstructured text responses.
        model (str, optional): The OpenAI model to use. Defaults to "gpt-4o-mini".

    Returns:
        str: The generated text response from the AI model

    Note:
        This function has a 10 second timeout applied through the @timeout decorator
    """
    client = OpenAI(api_key=api_key)
    if response_format is None:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )

    else:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            response_format=response_format,
        )

    return completion.choices[0].message.content


def format_html_message(plain_text):
    """
    Formats a plain text string as an HTML message.

    Args:
        plain_text (str): The plain text message to be formatted as HTML.

    Returns:
        str: The HTML-formatted message.
    """

    # Escape HTML special characters in the message
    plain_text = html.escape(plain_text)

    # Replace newlines with HTML line breaks
    html_text = plain_text.replace("\n", "<br>")

    # Wrap the message with HTML tags
    html_message = f"<p>{html_text}</p>"

    return html_message


def extract_text_between_tags(text, start_tag, end_tag):
    """
    Extracts text between specified start and end tags in a string.

    Args:
        text (str): The source text to search within
        start_tag (str): The opening tag or delimiter
        end_tag (str): The closing tag or delimiter

    Returns:
        str or None: The extracted text between tags if found, None otherwise
    """
    pattern = rf"{start_tag}(.*?){end_tag}"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1)
    else:
        return None


def classify_email(email: str):
    """
    Classifies an email into predefined categories using AI.

    This function sends the email content to an AI model to categorize it into one
    of several types (To respond, FYI, Comment, Notification, etc.) based on content analysis.

    Args:
        email (str): The email body text to classify

    Returns:
        dict: Classification result containing the email category label

    Note:
        If the email is too long, it will be truncated to LIMIT_EMAIL_LENGTH characters.
    """
    # if email body is too long, truncate it
    if len(email) > LIMIT_EMAIL_LENGTH:
        email = email[:LIMIT_EMAIL_LENGTH]

    prompt = f"""

    Classify the following email in one of these types:
    To respond
    Emails you need to respond to

    Fyi
    Emails that don't require your response, but are important

    Comment
    Team chats in tools like Google Docs or Microsoft Office

    Notification
    Automated updates from tools you use

    Meeting update
    Calendar updates from Zoom, Google Meet, etc

    Actioned
    Emails you've sent that you're not expecting a reply to

    Marketing
    Marketing or cold emails.
    
    Here is the email to classify:
    
    {email}
    
    """

    res = json.loads(generate_with_ai(prompt, response_format=EmailLabel))
    return res


class EmailResponse(BaseModel):
    subject_text: str
    email_body_text: str


def create_ai_draft_response(
    email_body: str,
    sender: str,
    receiver_name: str,
    email_subject: str,
):
    """
    Generates an AI-drafted email response based on the original email.

    This function creates a contextually appropriate reply to an email by providing
    the AI with the original email details. The response is crafted to match the
    sender's tone and is structured to be ready to send without further editing.

    Args:
        email_body (str): The content of the original email
        sender (str): The email address or name of the original sender
        receiver_name (str): The name of the person receiving the email (current user)
        email_subject (str): The subject line of the original email

    Returns:
        str: A complete email body text ready to be sent as a response
    """
    prompt = f"""Generate a reply to the following email:

    The response must be in the same language as the original email.

    It should match the sender's tone (formal/informal, professional/casual, etc.).

    The reply should be structured and ready to send without further modification.

    Email details:
    
    Sender: {sender}
    Receiver (me): {receiver_name}
    email_subject: {email_subject}
    email_body: {email_body}
    
    Craft a natural, well-structured response that aligns with the context and intent of the original message.
    It must be ready to send as is."""
    res = json.loads(generate_with_ai(prompt, response_format=EmailResponse))
    return res["email_body_text"]
