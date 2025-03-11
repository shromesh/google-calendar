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
