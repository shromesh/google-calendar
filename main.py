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

# dotenv で Slack Token などを読み込む (pip install python-dotenv)
from dotenv import load_dotenv

# カレンダー読み取りだけなら readonly で十分
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def get_user_credentials():
    """
    ユーザーとしてOAuth認証を行い、Credentials オブジェクトを返す。
    - 初回: ブラウザで認証フロー
    - 2回目以降: token.json を再利用 (pickle形式)
    """
    creds = None
    if os.path.exists("token.json"):
        with open("token.json", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # client_secret.json は Google Cloud Console で「デスクトップアプリ」などの
            # OAuthクライアントIDを作り、ダウンロードしたファイルを配置してください。
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secret.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # 認証完了したので保存
        with open("token.json", "wb") as token:
            pickle.dump(creds, token)

    return creds


def get_tomorrows_earliest_timed_event(service, timezone="Asia/Tokyo"):
    """
    与えられた Calendar API service (ユーザー認証済み) を使って、
    明日の "終日ではない" (dateTimeあり) イベントの中で一番早い予定を取得。
    戻り値: (予定名, イベント開始時刻[datetime])  または None
    """
    local_tz = pytz.timezone(timezone)

    # 明日の開始/終了 (ローカルタイム)
    today = dt.now(local_tz).date()
    tomorrow = today + timedelta(days=1)

    start_of_tomorrow_naive = datetime.datetime.combine(
        tomorrow, datetime.datetime.min.time()
    )
    end_of_tomorrow_naive = datetime.datetime.combine(
        tomorrow, datetime.datetime.max.time()
    )
    start_of_tomorrow = local_tz.localize(start_of_tomorrow_naive)
    end_of_tomorrow = local_tz.localize(end_of_tomorrow_naive)

    time_min = start_of_tomorrow.isoformat()  # 例: "2025-03-07T00:00:00+09:00"
    time_max = end_of_tomorrow.isoformat()

    # ログイン中のユーザー(primary)から予定を取得
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

    # 終日予定を除外 (start.dateTime があるものだけ残す)
    timed_events = []
    for e in events:
        # e['start'] が 'dateTime' を持つ場合は通常の予定
        if "dateTime" in e["start"]:
            timed_events.append(e)

    if not timed_events:
        return None

    # 最初(一番早い)予定を取得
    first_event = timed_events[0]
    summary = first_event.get("summary", "（無題）")

    # 開始時刻文字列 (例: "2025-03-07T09:00:00+09:00")
    start_time_str = first_event["start"]["dateTime"]
    # ISO8601をdatetimeに変換
    start_time = dt.fromisoformat(start_time_str)
    # ローカルタイムに変換
    start_time_local = start_time.astimezone(local_tz)

    return (summary, start_time_local)


def post_message_to_slack(token, channel, message):
    """
    Slack へメッセージを投稿する
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

    # 4. 明日の最初の "通常予定" (dateTimeあり) を取得
    event_info = get_tomorrows_earliest_timed_event(service, timezone)

    if event_info:
        summary, start_time = event_info
        start_str = start_time.strftime("%H:%M")
        message = f"明日の最初の予定は「{summary}」で、開始時刻は {start_str} です。"
        print(f"明日の最初の通常予定: {summary} ({start_time})")
    else:
        message = "明日の終日以外の予定はありません。"
        print("明日の通常予定はありません。")

    # 5. Slackへ投稿
    if slack_token:
        post_message_to_slack(slack_token, slack_channel, message)
    else:
        print("SLACK_BOT_TOKEN が見つかりません。Slack投稿はスキップします。")


if __name__ == "__main__":
    main()
