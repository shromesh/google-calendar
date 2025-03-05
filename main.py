import os
import json
import datetime
from datetime import datetime, timedelta
import pytz

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


def get_tomorrows_earliest_event_start_time(
    service_account_json_str: str, calendar_id: str, timezone: str = "Asia/Tokyo"
):
    """
    service_account_json_str: 環境変数から取得したサービスアカウントJSONの中身(文字列)
    calendar_id             : "primary" や "xxx@group.calendar.google.com" など
    timezone                : "Asia/Tokyo" など
    """
    # JSON文字列を Pythonのdict へ変換
    service_account_info = json.loads(service_account_json_str)

    # 資格情報を生成
    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    )
    # Calendar API クライアントを生成
    service = build("calendar", "v3", credentials=creds)

    # タイムゾーンを指定して "明日" の開始/終了日時を作る
    local_tz = pytz.timezone(timezone)
    today = datetime.now(local_tz).date()
    tomorrow = today + timedelta(days=1)

    # ナイーブなdatetimeを作ってから localize する
    start_of_tomorrow_naive = datetime.combine(tomorrow, datetime.min.time())
    end_of_tomorrow_naive = datetime.combine(tomorrow, datetime.max.time())
    start_of_tomorrow = local_tz.localize(start_of_tomorrow_naive)
    end_of_tomorrow = local_tz.localize(end_of_tomorrow_naive)

    # RFC3339形式 (タイムゾーン付き) で文字列を生成
    time_min = start_of_tomorrow.isoformat()
    time_max = end_of_tomorrow.isoformat()

    # ここで events を取得
    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    # --- ここから print 出力を追加 ---
    print("===== Google Calendar API Raw Response =====")
    print(events_result)

    events = events_result.get("items", [])
    print("===== events =====")
    print(events)

    if not events:
        return None

    # 最初のイベントを取得
    first_event = events[0]
    print("===== first_event =====")
    print(first_event)

    start_time_str = first_event["start"].get(
        "dateTime", first_event["start"].get("date")
    )

    # dateTime or 終日(date) で分岐
    if "T" in start_time_str:
        start_time = datetime.fromisoformat(
            start_time_str
        )  # 例: "2025-03-06T10:00:00+09:00"
    else:
        start_time = datetime.fromisoformat(start_time_str + "T00:00:00+00:00")

    # タイムゾーン変換
    start_time_local = start_time.astimezone(local_tz)
    return start_time_local


def post_message_to_slack(token: str, channel: str, message: str):
    client = WebClient(token=token)
    try:
        response = client.chat_postMessage(channel=channel, text=message)
        print("Slack へメッセージを投稿しました。")
        return response
    except SlackApiError as e:
        print(f"Slack へのメッセージ投稿に失敗しました: {e.response['error']}")
        return None


if __name__ == "__main__":
    load_dotenv()

    # サービスアカウント JSON (文字列) を読み取り
    service_account_json_str = os.getenv("GCP_SERVICE_ACCOUNT_CREDENTIALS", "")
    if not service_account_json_str:
        raise ValueError(
            "環境変数 'GCP_SERVICE_ACCOUNT_CREDENTIALS' がセットされていません。"
        )

    # カレンダーID, Slackトークンなどを読み取り
    calendar_id = os.getenv("CALENDAR_ID", "primary")
    slack_bot_token = os.getenv("SLACK_BOT_TOKEN", "")
    slack_channel = os.getenv("SLACK_CHANNEL", "#general")
    timezone = os.getenv("TIMEZONE", "Asia/Tokyo")

    # 明日の最初の予定を取得
    earliest_event_start = get_tomorrows_earliest_event_start_time(
        service_account_json_str=service_account_json_str,
        calendar_id=calendar_id,
        timezone=timezone,
    )

    # Slack通知メッセージ
    if earliest_event_start:
        hour_str = earliest_event_start.strftime("%H時%M分")
        message = f"明日は {hour_str} にアラームをかけてください。"
    else:
        message = "明日は予定がありません。"

    # Slack へ投稿 (Botがチャンネルに居ないと not_in_channel になる)
    if slack_bot_token:
        post_message_to_slack(slack_bot_token, slack_channel, message)
    else:
        print("SLACK_BOT_TOKEN が見つからないため、Slack への投稿は実行されません。")
