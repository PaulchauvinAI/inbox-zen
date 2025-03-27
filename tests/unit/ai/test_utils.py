from email_assistant.ai.utils import create_ai_draft_response, classify_email
from email_assistant.config import FOLDERS

meeting_update_var = "Meeting Update"


def test_classify_email():
    assert meeting_update_var in FOLDERS
    email = "finally I'm not available at this time, changing meeting to 11pm"
    assert classify_email(email)["label"] == meeting_update_var


def test_create_ai_draft_response():
    email_body = "hey Paul, how are you doing today? did you have time to check my previous email? Jacques"
    sender = "jacques"
    email_subject = "update"
    receiver_name = "Paul"
    draft = create_ai_draft_response(email_body, sender, receiver_name, email_subject)
    assert draft is not None
    assert len(draft) > 10
