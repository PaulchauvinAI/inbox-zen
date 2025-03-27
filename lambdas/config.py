# AWS CONFIG

AWS_REGION = "eu-central-1"

# LAMBDA FUNCTIONS

LAMBDA_FUNCTIONS = {
    "update_inbox": "check_new_msgs",
    "cron_job": "trigger_update_inbox",
}
