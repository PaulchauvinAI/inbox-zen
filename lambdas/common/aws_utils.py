from boto3 import client as boto3_client
import json
from lambdas.config import AWS_REGION


def call_lambda_function(parameters, function_name: str, region=AWS_REGION):
    lambda_client = boto3_client("lambda", region_name=region)
    invoke_response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="Event",
        Payload=json.dumps(parameters),
    )
    return {"response": invoke_response}
