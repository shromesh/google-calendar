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
    環境変数に格納された "サービスアカウントJSON文字列" を直接使って、
    GoogleカレンダーAPIから「明日」最初の予定を取得して開始時刻を返す。
    """

    # 1. 環境変数から JSON 文字列を読み込み → dict に変換
    service_account_info = json.loads(service_account_json_str)

    # 2. dict 情報から Google の資格情報を生成
    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    )

    # 3. Calendar API のクライアントを生成
    service = build("calendar", "v3", credentials=creds)

    # 4. 明日の日付の開始と終了を取得
    local_tz = pytz.timezone(timezone)
    today = datetime.now(local_tz).date()
    tomorrow = today + timedelta(days=1)
    start_of_tomorrow = datetime.combine(tomorrow, datetime.min.time())
    end_of_tomorrow = datetime.combine(tomorrow, datetime.max.time())

    # 取得範囲をISO8601形式に変換
    time_min = start_of_tomorrow.isoformat()
    time_max = end_of_tomorrow.isoformat()

    # 5. カレンダーイベントを取得
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

    # 6. 最初(一番早い)イベントを取得
    first_event = events[0]
    start_time_str = first_event["start"].get(
        "dateTime", first_event["start"].get("date")
    )

    # 7. dateTime or 終日 (date) で分岐してパース
    if "T" in start_time_str:
        start_time = datetime.fromisoformat(start_time_str)
    else:
        start_time = datetime.fromisoformat(start_time_str + "T00:00:00+00:00")

    # 8. タイムゾーン変換
    start_time_local = start_time.astimezone(local_tz)
    return start_time_local


def post_message_to_slack(token: str, channel: str, message: str):
    """
    Slack へメッセージを投稿する
    """
    client = WebClient(token=token)
    try:
        response = client.chat_postMessage(channel=channel, text=message)
        return response
    except SlackApiError as e:
        print(f"Slack へのメッセージ投稿に失敗しました: {e.response['error']}")


if __name__ == "__main__":
    load_dotenv()

    # =============================
    # 環境変数から必要な情報を取得
    # =============================
    # GCP_SERVICE_ACCOUNT_CREDENTIALS に JSON 本体が入っている前提
    service_account_json_str = os.getenv("GCP_SERVICE_ACCOUNT_CREDENTIALS", "")
    if not service_account_json_str:
        raise ValueError(
            "環境変数 GCP_SERVICE_ACCOUNT_CREDENTIALS が設定されていません。"
        )

    # カレンダーID, Slackトークンなど
    calendar_id = os.getenv("CALENDAR_ID", "primary")
    slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
    slack_channel = os.getenv("SLACK_CHANNEL", "#general")
    timezone = os.getenv("TIMEZONE", "Asia/Tokyo")

    # =============================
    # 明日の最初の予定を取得
    # =============================
    earliest_event_start = get_tomorrows_earliest_event_start_time(
        service_account_json_str=service_account_json_str,
        calendar_id=calendar_id,
        timezone=timezone,
    )

    # =============================
    # Slack に投稿
    # =============================
    if earliest_event_start:
        hour_str = earliest_event_start.strftime("%H時%M分")  # "09時00分" 等
        message = f"明日は {hour_str} にアラームをかけてください。"
    else:
        message = "明日は予定がありません。"

    if slack_bot_token:
        post_message_to_slack(slack_bot_token, slack_channel, message)
        print("Slack へメッセージを投稿しました。")
    else:
        print("SLACK_BOT_TOKEN が見つからないため、Slack への投稿はスキップしました。")
