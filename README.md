# google-calendar

# CLIにログイン
gcloud auth application-default login

# lambdaで実行するときの認証
- ローカルで`auth.sh`を実行
    - Calendarへのログイントークンの更新とSecrets Managerへのアップロードが行われる
- ECRを作成し、push（以下参考）
- Lambdaを作成し、実行ロールを付与
```
{
  "Effect": "Allow",
  "Action": [
    "secretsmanager:GetSecretValue"
  ],
  "Resource": "*"
}
```

# アカウント
- AWS(ECR, Lambda, Secrets Manager)
    - prefab-admin
- GCP(Calendar API, OAuth)
    - yonemoto
    - alarm-automation

# docker
```
# レポジトリ名など
export IMAGE_NAME=my-lambda-calendar:latest
export LAMBDA_NAME=my-lambda-calendar
export ECR_URI=950942770806.dkr.ecr.ap-northeast-1.amazonaws.com/my-lambda-calendar:latest
export ACCOUNT_ID=950942770806
export PROFILE=prefab-admin

# x86_64 用イメージをビルド
docker build --platform=linux/amd64 --pull --no-cache -t $IMAGE_NAME .
docker tag $IMAGE_NAME $ECR_URI
aws ecr get-login-password --region ap-northeast-1 --profile $PROFILE \
    | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.ap-northeast-1.amazonaws.com
docker push $ECR_URI
aws lambda update-function-code --profile $PROFILE --function-name $LAMBDA_NAME --image-uri $ECR_URI
