# Lambda Python 3.9 公式ベースイメージ
FROM public.ecr.aws/lambda/python:3.9

# 作業ディレクトリを設定
WORKDIR /var/task

# 必要ファイルをコピー
COPY requirements.txt ./
COPY main.py ./

# Pythonライブラリをインストール (Lambdaの /var/task に)
RUN pip3 install --upgrade pip && \
    pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Lambda 実行時に呼び出されるハンドラを指定
CMD ["app.lambda_handler"]
