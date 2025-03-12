#!/bin/bash

export PROFILE=prefab-admin
source .venv/bin/activate

# 1. ローカルで OAuth 認証を実行（token.json を更新）
python app_local_oauth.py

# 2. token.json を base64 エンコード
base64_token=$(base64 token.json)

# 3. 念のため、どの認証情報を使っているか表示
aws sts get-caller-identity --profile $PROFILE

# 4. すでに "my_calendar_token" が存在するかチェック
echo "Checking if 'my_calendar_token' secret already exists..."
if aws secretsmanager describe-secret --profile "$PROFILE" --secret-id "my_calendar_token" --region ap-northeast-1 > /dev/null 2>&1; then
  # シークレットが既に存在するので、値を上書きする
  echo "Secret 'my_calendar_token' exists. Updating..."
  aws secretsmanager put-secret-value \
    --profile "$PROFILE" \
    --secret-id "my_calendar_token" \
    --region ap-northeast-1 \
    --secret-string "{\"token\":\"$base64_token\"}"
else
  # シークレットが存在しないので、新規作成
  echo "Secret 'my_calendar_token' does not exist. Creating..."
  aws secretsmanager create-secret \
    --profile "$PROFILE" \
    --name "my_calendar_token" \
    --region ap-northeast-1 \
    --secret-string "{\"token\":\"$base64_token\"}"
fi
