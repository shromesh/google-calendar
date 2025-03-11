from __future__ import print_function

import os
import pickle
import sys
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# カレンダー読み取りだけなら readonly でOK
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def main():
    creds = None
    token_file = "token.json"

    # もし既に token.json があれば、そこから読み込む
    if os.path.exists(token_file):
        with open(token_file, "rb") as token:
            creds = pickle.load(token)

    # トークンがない or 期限切れならフローを走らせる
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("トークンが期限切れなのでリフレッシュします...")
            creds.refresh(Request())
        else:
            print("初回認証フローを開始します...")
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secret.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        # 新しいトークンを保存
        with open(token_file, "wb") as token:
            pickle.dump(creds, token)
        print(f"トークンを {token_file} に保存しました。")
    else:
        print("既存トークンが有効です。")

    # この時点で token.json に有効なアクセストークン・リフレッシュトークンが保存される
    print("OAuth認証が完了しました。")


if __name__ == "__main__":
    main()
