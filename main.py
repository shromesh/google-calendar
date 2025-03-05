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
    # 環境変数から JSON を読み取り、dict化
    import json

    service_account_info = json.loads(service_account_json_str)

    # サービスアカウント認証
    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    )
    service = build("calendar", "v3", credentials=creds)

    # タイムゾーンを生成
    local_tz = pytz.timezone(timezone)

    # 今日と明日を取得
    today = datetime.now(local_tz).date()
    tomorrow = today + timedelta(days=1)

    # 「明日」の開始・終了を「タイムゾーンつき」で作成
    start_of_tomorrow_naive = datetime.combine(tomorrow, datetime.min.time())
    end_of_tomorrow_naive = datetime.combine(tomorrow, datetime.max.time())

    # pytz を使って「アウェア」な datetime にする
    start_of_tomorrow = local_tz.localize(start_of_tomorrow_naive)
    end_of_tomorrow = local_tz.localize(end_of_tomorrow_naive)

    # RFC3339形式 (例: 2025-03-06T00:00:00+09:00) で文字列化
    time_min = start_of_tomorrow.isoformat()
    time_max = end_of_tomorrow.isoformat()

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
    events = events_result.get("items", [])

    if not events:
        return None

    # 最初のイベント
    first_event = events[0]
    start_time_str = first_event["start"].get(
        "dateTime", first_event["start"].get("date")
    )

    if "T" in start_time_str:
        # 例: "2025-03-06T10:00:00+09:00"
        start_time = datetime.fromisoformat(start_time_str)
    else:
        # 終日 (date形式 "2025-03-06") の場合は 00:00:00+00:00 としてパースし、
        # その後ローカルタイムに変換
        start_time = datetime.fromisoformat(start_time_str + "T00:00:00+00:00")

    start_time_local = start_time.astimezone(local_tz)
    return start_time_local


def post_message_to_slack(token: str, channel: str, message: str):
    client = WebClient(token=token)
    try:
        response = client.chat_postMessage(channel=channel, text=message)
        return response
    except SlackApiError as e:
        print(f"Slack へのメッセージ投稿に失敗しました: {e.response['error']}")


if __name__ == "__main__":
    load_dotenv()

    service_account_json_str = os.getenv("GCP_SERVICE_ACCOUNT_CREDENTIALS", "")
    if not service_account_json_str:
        raise ValueError(
            "環境変数 GCP_SERVICE_ACCOUNT_CREDENTIALS がセットされていません。"
        )

    calendar_id = os.getenv("CALENDAR_ID", "primary")
    slack_bot_token = os.getenv("SLACK_BOT_TOKEN", "")
    slack_channel = os.getenv("SLACK_CHANNEL", "#general")
    timezone = os.getenv("TIMEZONE", "Asia/Tokyo")

    earliest_event_start = get_tomorrows_earliest_event_start_time(
        service_account_json_str=service_account_json_str,
        calendar_id=calendar_id,
        timezone=timezone,
    )

    if earliest_event_start:
        hour_str = earliest_event_start.strftime("%H時%M分")
        message = f"明日は {hour_str} にアラームをかけてください。"
    else:
        message = "明日は予定がありません。"

    if slack_bot_token:
        post_message_to_slack(slack_bot_token, slack_channel, message)
        print("Slack へメッセージを投稿しました。")
    else:
        print("SLACK_BOT_TOKEN が見つからないため、Slack への投稿はスキップしました。")
