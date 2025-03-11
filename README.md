# google-calendar

gcloud auth application-default login

# 認証ファイル
```
# 1回目
client_secret.json
# 2回目
token.json
```

# lambdaで実行するときの認証
- ローカルで`auth.sh`を実行
    - トークンの更新とアップロードが行われる

# アカウント
- AWS(ECR, Lambda, Secrets Manager)
    - prefab-admin
- GCP(Calendar API, OAuth)
    - yonemoto
    - alarm-automation

# docker
```
# 前提：GUIでECRを作成済み(レポジトリ名：my-lambda-calendar)
docker build -t my-lambda-calendar:latest .
docker tag my-lambda-calendar:latest <your_ecr_repo_uri>:latest
aws ecr get-login-password --region ap-northeast-1 --profile prefab-admin \
    | docker login --username AWS --password-stdin <your_account_id>.dkr.ecr.ap-northeast-1.amazonaws.com
docker push <your_ecr_repo_uri>:latest
```

# test
```
docker run -p 9000:8080 my-lambda-calendar:latest
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
     -d '{}'
```