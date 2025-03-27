from lambdas.common.aws_utils import call_lambda_function
from email_assistant.db.operations import get_df_from_query
from email_assistant.db.utils import cleanup_db_resources
from lambdas.config import LAMBDA_FUNCTIONS


def handler(event, context):
    try:
        df = get_df_from_query(
            "select * from email_accounts where disconnected = False"
        )
        for _, row in df.iterrows():
            call_lambda_function(
                {"email_account": row.email, "action": "update_inbox"},
                function_name=LAMBDA_FUNCTIONS["update_inbox"],
            )
    finally:
        cleanup_db_resources()
