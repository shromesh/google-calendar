export PROFILE=prefab-admin
source .venv/bin/activate
python app_local_oauth.py
base64_token=$(base64 token.json)
aws sts get-caller-identity --profile $PROFILE
aws secretsmanager create-secret \
    --profile $PROFILE \
    --name my_calendar_token \
    --region ap-northeast-1 \
    --secret-string "{\"token\":\"$base64_token\"}"
