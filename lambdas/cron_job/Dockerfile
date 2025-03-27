FROM public.ecr.aws/lambda/python:3.9

COPY requirements.txt requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

# for aws lambda
COPY email_assistant/ email_assistant/
COPY lambdas/ lambdas/
COPY .env email_assistant/.env
COPY lambdas/cron_job/handler.py lambda_function.py
CMD [ "lambda_function.handler" ]