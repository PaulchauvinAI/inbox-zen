from lambdas.common.aws_utils import call_lambda_function
from lambdas.config import LAMBDA_FUNCTIONS


def test_call_lambda_function():
    call_lambda_function({}, function_name=LAMBDA_FUNCTIONS["cron_job"])
