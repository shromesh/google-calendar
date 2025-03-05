from __future__ import print_function

import os
import pickle
import datetime
from datetime import datetime as dt, timedelta
import pytz
import dateutil.parser

# Slack 用
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# OAuth 用
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

# dotenv で Slack Token などを読み込む
# pip install python-dotenv
from dotenv import load_dotenv

# カレンダー読み取りだけなら readonly で十分
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def get_user_credentials():
    """
    ユーザーとしてOAuth認証を行い、Credentials オブジェクトを返す。
    - 初回: ブラウザで認証フロー
    - 2回目以降: token.json を再利用
    """
    creds = None

    # すでに token.json があれば、そこから読み込む (pickle形式)
    if os.path.exists("token.json"):
        with open("token.json", "rb") as token:
            creds = pickle.load(token)

    # キャッシュが無い or 期限切れ の場合は認証フロー
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # リフレッシュトークンがあれば更新
            creds.refresh(Request())
        else:
            # 新規に OAuth フロー開始
            # client_secret.json は Google Cloud Console で「デスクトップアプリ」などを選択し、
            # ダウンロードしたファイルを配置したもの。
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secret.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        # 認証完了したので token.json に保存
        with open("token.json", "wb") as token:
            pickle.dump(creds, token)

    return creds


def get_tomorrows_earliest_event_start_time(service, timezone="Asia/Tokyo"):
    """
    与えられた Calendar API service (ユーザー認証済み) を使って、
    明日の最も早い予定開始時刻を返す (なければ None)
    """
    # タイムゾーン設定
    local_tz = pytz.timezone(timezone)

    # 今日 + 1日 = 明日
    today = dt.now(local_tz).date()
    tomorrow = today + timedelta(days=1)

    # 明日 0:00 と 23:59:59.999... (ローカルタイム) を作成
    start_of_tomorrow_naive = datetime.datetime.combine(
        tomorrow, datetime.datetime.min.time()
    )
    end_of_tomorrow_naive = datetime.datetime.combine(
        tomorrow, datetime.datetime.max.time()
    )

    # pytz でローカルタイムに変換 (アウェアなdatetimeを作成)
    start_of_tomorrow = local_tz.localize(start_of_tomorrow_naive)
    end_of_tomorrow = local_tz.localize(end_of_tomorrow_naive)

    # RFC3339形式で文字列化
    time_min = start_of_tomorrow.isoformat()
    time_max = end_of_tomorrow.isoformat()

    # "primary" (ログインしたユーザーのメインカレンダー) から、明日のイベントを取得
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = events_result.get("items", [])

    if not events:
        return None

    # 最初(一番早い)イベントを取り出す
    first_event = events[0]
    start_time_str = first_event["start"].get(
        "dateTime", first_event["start"].get("date")
    )

    # 終日予定の場合は "date" フィールドのみ
    if "T" in start_time_str:
        # 例: "2025-03-06T10:00:00+09:00"
        start_time = dt.fromisoformat(start_time_str)
    else:
        # 終日 (yyyy-mm-dd 形式) → 00:00として処理し、UTC扱い→ローカルに変換
        start_time = dt.fromisoformat(start_time_str + "T00:00:00+00:00")

    start_time_local = start_time.astimezone(local_tz)
    return start_time_local


def post_message_to_slack(token, channel, message):
    """
    Slack にメッセージを投稿する
    """
    client = WebClient(token=token)
    try:
        response = client.chat_postMessage(channel=channel, text=message)
        print("Slack へメッセージを投稿しました。")
        return response
    except SlackApiError as e:
        print(f"Slack へのメッセージ投稿に失敗しました: {e.response['error']}")
        return None


def main():
    # 1. .env から Slackトークン等を読み込む
    load_dotenv()
    slack_token = os.getenv("SLACK_BOT_TOKEN", "")
    slack_channel = os.getenv("SLACK_CHANNEL", "#general")
    timezone = os.getenv("TIMEZONE", "Asia/Tokyo")

    # 2. OAuth 認証 (ユーザーとして)
    creds = get_user_credentials()

    # 3. 認証済みクレデンシャルで Calendar API Service を作成
    service = build("calendar", "v3", credentials=creds)

    # 4. 明日の最初の予定を取得
    earliest_event_start = get_tomorrows_earliest_event_start_time(service, timezone)

    if earliest_event_start:
        hour_str = earliest_event_start.strftime("%H時%M分")
        message = f"明日は {hour_str} にアラームをかけてください。"
        print(f"明日の最初の予定開始時刻: {earliest_event_start} (ローカルタイム)")
    else:
        message = "明日は予定がありません。"
        print("明日の予定はありません。")

    # 5. Slackへ投稿
    if slack_token:
        post_message_to_slack(slack_token, slack_channel, message)
    else:
        print("SLACK_BOT_TOKEN が見つかりません。Slack投稿はスキップします。")


if __name__ == "__main__":
    main()
