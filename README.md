# google-calendar

# CLIにログイン
gcloud auth application-default login

# lambdaで実行するときの認証
- auth.shを開き、前半の変数部分を変更
- ローカルで`./auth.sh`を実行
    - Calendarへのログイントークンの更新とSecrets Managerへのアップロードが行われる
- ECRを作成
- Lambdaを作成し、実行ロールを付与
```
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:PutSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:ap-northeast-1:950942770806:secret:my_calendar_token-*"
    }
  ]
}
```

# アカウント
- AWS(ECR, Lambda, API Gateway, Secrets Manager)
    - prefab-admin
- GCP(Calendar API, OAuth)
    - yonemoto
    - alarm-automation

# デプロイ
- push.shを開き、前半の変数部分を変更
- `./push.sh`を実行
