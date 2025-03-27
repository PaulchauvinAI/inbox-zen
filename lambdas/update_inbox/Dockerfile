FROM public.ecr.aws/lambda/python:3.9

COPY requirements.txt requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY email_assistant/ email_assistant/
COPY .env email_assistant/.env
COPY lambdas/ lambdas/
COPY lambdas/update_inbox/handler.py lambda_function.py
CMD [ "lambda_function.handler" ]