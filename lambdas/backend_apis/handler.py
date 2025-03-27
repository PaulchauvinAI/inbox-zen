from fastapi import FastAPI, HTTPException, Depends, Header
from mangum import Mangum
from email_assistant.db.operations import insert_new_email
from pydantic import BaseModel, EmailStr
from email_assistant.email_scripts.imap_account.check_connection import (
    check_imap_access,
)
from email_assistant.email_scripts.outlook_account.outlook_connection import (
    auth_step_1,
    auth_step_2,
)
from email_assistant.db.utils import cleanup_db_resources
from email_assistant.db.operations import get_df_from_query
from lambdas.common.aws_utils import call_lambda_function
from email_assistant.email_scripts.revert_inbox import revert_inbox
from dotenv import load_dotenv
import os
from lambdas.config import LAMBDA_FUNCTIONS
from typing import Optional, Dict, Any

load_dotenv()
app = FastAPI()
handler = Mangum(app)

api_key_name = "X-API-KEY"


API_KEY = os.getenv("API_KEY")


async def require_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


class Imap_creds(BaseModel):
    imap_pwd: str
    imap_login: str


class ResponseData(BaseModel):
    data: Dict[str, Any]
    message: Optional[str] = None


@app.post(
    "/add_imap_email",
    dependencies=[Depends(require_api_key)],
    response_model=ResponseData,
)
async def add_imap_email(
    user_id: str,
    creds: Imap_creds,
    imap_server: str = "imap.gmail.com",
    imap_port: int = 993,
):
    try:
        query = f"select * from email_accounts where imap_login = '{creds.imap_login}'"
        email_in_db = len(get_df_from_query(query)) > 0

        imap_correct, imap_error = check_imap_access(
            sender_email=creds.imap_login,
            password=creds.imap_pwd,
            imap_server=imap_server,
            imap_port=imap_port,
        )

        if not imap_correct:
            raise HTTPException(status_code=400, detail=imap_error)

        if not email_in_db:
            insert_new_email(
                creds.imap_login,
                user_id,
                imap_login=creds.imap_login,
                imap_pwd=creds.imap_pwd,
                imap_server=imap_server,
                imap_port=imap_port,
                email_provider="Gmail",
            )

        call_lambda_function(
            {"email_account": creds.imap_login, "action": "update_inbox"},
            function_name=LAMBDA_FUNCTIONS["update_inbox"],
        )

        if email_in_db:
            raise HTTPException(
                status_code=400, detail="Email already exists in database"
            )
        return ResponseData(data={"email": creds.imap_login})

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cleanup_db_resources()


@app.post(
    "/revert_inbox_",
    dependencies=[Depends(require_api_key)],
    response_model=ResponseData,
)
async def revert_inbox_(email_account: EmailStr):
    try:
        # revert_inbox(email_account)
        call_lambda_function(
            {"email_account": email_account, "action": "revert_inbox"},
            function_name=LAMBDA_FUNCTIONS["update_inbox"],
        )
        return ResponseData(
            data={"email": email_account},
            message=f"Inbox reverted successfully for {email_account}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Outlook APIs
class OutlookAuthStep1Params(BaseModel):
    user_id: str
    is_test: bool = False


@app.post(
    "/outlook_auth_step_1",
    dependencies=[Depends(require_api_key)],
    response_model=ResponseData,
)
async def outlook_auth_step_1(params: OutlookAuthStep1Params):
    try:
        consent_url, state = auth_step_1(params.user_id, params.is_test)
        return ResponseData(data={"consent_url": consent_url, "state": state})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class OutlookAuthStep2Params(BaseModel):
    user_id: str
    token_url: str
    is_test: bool = False


@app.post(
    "/outlook_auth_step_2",
    dependencies=[Depends(require_api_key)],
    response_model=ResponseData,
)
async def outlook_auth_step_2(params: OutlookAuthStep2Params):
    try:
        result, email_to_connect = auth_step_2(
            params.token_url, params.user_id, params.is_test
        )

        if not result:
            raise HTTPException(status_code=400, detail="Authentication failed")

        call_lambda_function(
            {"email_account": email_to_connect},
            function_name=LAMBDA_FUNCTIONS["update_inbox"],
        )
        return ResponseData(
            data={"email": email_to_connect}, message="Email connected successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error connecting your email: {e}, try again"
        )
