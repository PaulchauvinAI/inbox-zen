# Inbox Zen - Email Assistant

![Inbox Zen Logo](https://inbox-zen.com/assets/logo.png)

## Overview

Inbox Zen is an intelligent email management platform that helps you regain control of your inbox. Our solution connects to your email accounts (Gmail, Outlook) and applies AI-powered organization to keep your inbox clean, organized, and stress-free.

## Features

* **Multi-provider Support**: Connect Gmail and Outlook accounts
* **Smart Email Organization**: Automatically categorize and organize incoming emails
* **Email Assistants**: AI-powered assistants that help manage your emails
* **Email Rollback**: Ability to revert inbox changes if needed
* **Secure Connection**: OAuth-based authentication for maximum security
* **Serverless Architecture**: Reliable, scalable AWS Lambda-based backend

## Repository Structure

```
email_assistant/
├── .env                     # Environment variables (add your own values)
├── .gitignore               # Git ignore file
├── README.md                # This document
├── README_INTERNAL.md       # Internal documentation
├── database_migration.sql   # SQL migrations for database setup
├── pytest.ini               # Pytest configuration
├── requirements.txt         # Project dependencies
├── template.env             # Template for .env file
├── update_lambdas.sh        # Script to deploy Lambda functions
│
├── email_assistant/         # Main package
│   ├── __init__.py
│   ├── config.py            # Configuration settings
│   ├── ai/                  # AI-related functionality
│   ├── db/                  # Database interactions
│   ├── email_scripts/       # Email processing scripts
│   └── utils/               # Utility functions
│
├── lambdas/                 # AWS Lambda functions
│   ├── __init__.py
│   ├── config.py
│   ├── backend_apis/        # API endpoints implementations (email_assistant_apis)
│   ├── common/              # Shared Lambda code
│   ├── cron_job/            # Scheduled tasks (trigger_update_inbox)
│   └── update_inbox/        # Inbox update functionality (check_new_msgs)
│
└── tests/                   # Test suite
    └── unit/                # Unit tests
```

## Getting Started

### Prerequisites

- Python 3.8+
- AWS CLI configured with appropriate credentials
- PostgreSQL database
- FastAPI
- Required Python packages (see requirements.txt)

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/email_assistant.git
cd email_assistant
```

2. Set up environment variables
```bash
cp template.env .env
# Edit .env with your configuration values
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

### Development

Before making any changes, ensure all tests pass:
```bash
pytest tests/
```

To run the APIs locally:

```bash
python3 -m uvicorn lambdas.backend_apis.handler:app --reload --port 8081
```

### Deployment

Deploy the Lambda functions to AWS:

```bash
bash update_lambdas.sh
```

## Self-Hosting Guide

### Prerequisites
- AWS account with appropriate permissions
- PostgreSQL database (Supabase or other provider)
- Git
- AWS CLI configured on your machine

### Installation Steps

#### 1. Clone the Repository
```bash
git clone https://github.com/PaulchauvinAI/inbox-zen
```

#### 2. Database Setup
- Create a PostgreSQL database instance. You can use any provider, but Supabase is free and easy to set up.
- Import the schema using the provided migration file:
  - Open the database query browser
  - Copy and execute the contents of `database_migration.sql`

#### 3. Environment Configuration
- Copy the template environment file:
  ```bash
  cp template.env .env
  ```
- Edit `.env` with your AWS credentials and other required configuration

#### 4. AWS Configuration

##### 4.1 Configure AWS CLI
```bash
aws configure
```

##### 4.2 Create ECR Repositories
In the AWS Console:
- Create ECR repositories with these names:
  - email_assistant_apis (code for the APIs, connect an email account, revert an email account, ...)
  - check_new_msgs (API that update the inbox)
  - trigger_update_inbox (cron job API that triggers the update of the inbox)

##### 4.3 Build and Push Docker Images
```bash
./update_lambdas.sh --ecr-only
```

##### 4.4 Create Lambda Functions
In the AWS Lambda Console:
- Create lambda functions with identical names to your ECR repositories
- For each function:
  - Set memory allocation to 256MB
  - Set timeout to 150 seconds
  - Configure execution roles with permissions to call other lambda functions

Update email_assistant/config.py with the correct values

### Maintenance

#### Updating Lambda Functions
To update the lambda functions with new code:
```bash
./update_lambdas.sh
```

## API Documentation

The service provides several REST APIs:

### Email Management
- `/add_imap_email`: Connect a new IMAP-based email account
- `/revert_inbox`: Revert all changes made to an inbox and remove email account from the database

### Outlook Authentication
- `/outlook_auth_step_1`: Initiate OAuth flow for Outlook
- `/outlook_auth_step_2`: Complete OAuth flow for Outlook

### API Authentication

All API endpoints require authentication using the `x-api-key` header. Use the value of the `API_KEY` variable from your `.env` file.

Example:
```bash
curl -H "x-api-key: your_api_key" https://your-lambda-endpoint.com/path
```

## Architecture

The system is built on:
- AWS Lambda for serverless execution
- FastAPI for API development
- IMAP for Gmail connectivity
- Microsoft Graph API for Outlook connectivity (via O365 library)
- OpenAI for AI-powered email processing

## Testing

Run tests with pytest:

```bash
pytest tests/
```

## Security

- No email credentials are stored in plain text
- OAuth authentication is used for Outlook
- API key required for all endpoints
- Encrypted storage of sensitive information

## License

GNU Affero General Public License (AGPLv3) - See LICENSE file for details.

## Visit Us

[https://inbox-zen.com](https://inbox-zen.com)

---

Stay zen with your inbox!
