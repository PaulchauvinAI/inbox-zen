from email_assistant.email_scripts.outlook_account.utils_outlook import (
    get_account,
    save_text_to_s3,
)
from email_assistant.config import BUCKET_NAME, FOLDER_NAME
import json
from email_assistant.db.operations import insert_from_df
import pandas as pd
from email_assistant.db.utils import get_engine
from email_assistant.db.operations import insert_new_email

from typing import Tuple

from email_assistant.config import REDIRECT_URI_LIVE, REDIRECT_URI_TEST


def get_state(user_id: str):
    engine = get_engine()
    query = f"""SELECT * FROM outlook_states WHERE user_id = '{user_id}' ORDER BY created_at DESC 
    LIMIT 1"""
    with engine.connect() as conn:
        return pd.read_sql(query, con=conn)


def auth_step_1(user_id: str, test: bool = False) -> Tuple[str, str]:
    """Starts the Outlook authentification process.

    Args:
        email (str): The email address to be authenticated.
        user_id (str): The user's id.
        test (bool, optional): Whether to use the test redirect URI. Defaults to False.

    Returns:
        Tuple[str, str]: The authorization URL and the state.
    """
    redirect_uri = REDIRECT_URI_TEST if test else REDIRECT_URI_LIVE
    account = get_account()

    consent_url, state = account.con.get_authorization_url(redirect_uri=redirect_uri)

    # save state in the database with the user email

    df = pd.DataFrame({"state": [state], "user_id": [user_id]})
    insert_from_df(df, "outlook_states")
    return consent_url, state


def auth_step_2(token_url: str, user_id: str, is_test: bool = False):
    redirect_uri = REDIRECT_URI_TEST if is_test else REDIRECT_URI_LIVE
    states = get_state(user_id)
    # retrieve the last state associated to the user email:
    if len(states) != 1:
        raise ValueError("no state for this address")
    state = states.iloc[0].state
    account = get_account()
    result = account.con.request_token(
        token_url, state=state, redirect_uri=redirect_uri, store_token=False
    )
    if not result:
        raise ValueError("authentification did not work")
    email_to_connect = account.get_current_user().mail
    # save token in s3
    file_path = f"s3://{BUCKET_NAME}/{FOLDER_NAME}/{email_to_connect}.txt"
    token_to_save = account.con.token_backend.token

    save_text_to_s3(file_path, json.dumps(token_to_save))

    insert_new_email(email_to_connect, user_id, "outlook")
    return result, email_to_connect


if __name__ == "__main__":
    # usage example
    user_id = "****"  # user id in the database
    step_1 = True
    if step_1:
        consent_url, state = auth_step_1(user_id)
        print(consent_url)
    else:
        token_url = ""  # url that we get after redirection
        message = auth_step_2(token_url, user_id)
        print(message)
