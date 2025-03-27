#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
  # Use set -a to automatically export all variables defined
  set -a
  # Source the .env file, ignoring comments
  source <(grep -v '^#' .env)
  set +a
  echo "Loaded environment variables from .env file."
else
  echo ".env file not found. Using default values."
fi

# Set default values if not provided in .env
if [ -z "$AWS_REGION" ]; then
  AWS_REGION="eu-central-1"
  echo "AWS_REGION not found in .env, using default: $AWS_REGION"
fi

if [ -z "$AWS_ACCOUNT_ID" ]; then
  echo "ERROR: AWS_ACCOUNT_ID is not set in .env file. Please add it and try again."
  exit 1
fi

IMAGE_TAG="v0"
DEPLOY_TO_LAMBDA=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --ecr-only)
      DEPLOY_TO_LAMBDA=false
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--ecr-only]"
      exit 1
      ;;
  esac
done

# Function to build, push and update a lambda
update_lambda() {
  local name=$1
  local dockerfile_path=$2
  
  echo "Building ${name} lambda..."
  docker build -f ${dockerfile_path} -t ${name} .

  echo "Pushing ${name} to ECR..."
  aws ecr get-login-password --region ${AWS_REGION} --no-cli-pager | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
  docker tag ${name}:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${name}:${IMAGE_TAG}
  docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${name}:${IMAGE_TAG}

  if [ "$DEPLOY_TO_LAMBDA" = true ]; then
    echo "Updating ${name} lambda function..."
    aws lambda update-function-code --function-name ${name} --image-uri ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${name}:${IMAGE_TAG} --no-cli-pager
    echo "✅ ${name} lambda updated successfully!"
  else
    echo "✅ ${name} pushed to ECR successfully!"
  fi
  echo
}

# Update all lambdas
update_lambda "email_assistant_apis" "lambdas/backend_apis/Dockerfile"
update_lambda "check_new_msgs" "lambdas/update_inbox/Dockerfile"
update_lambda "trigger_update_inbox" "lambdas/cron_job/Dockerfile"
