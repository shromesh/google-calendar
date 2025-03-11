from __future__ import print_function

import os
import json
import base64
import pickle
import datetime
from datetime import datetime as dt, timedelta

import boto3
import pytz

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# dotenv が必要なら使用（Lambda では不要なら削除してOK）
from dotenv import load_dotenv


SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def load_credentials_from_secrets_manager(secret_name, region_name):
    """
    AWS Secrets Manager からトークン情報を取得し、pickleで Credentials を復元。
    - SecretString は例として {"token": "base64エンコードしたバイナリ"} の形とする。
    - もしトークンが期限切れなら creds.refresh() して再保存する。
    """
    client = boto3.client("secretsmanager", region_name=region_name)
    response = client.get_secret_value(SecretId=secret_name)
    secret_string = response["SecretString"]

    data = json.loads(secret_string)
    if "token" not in data:
        raise ValueError(
            f"Secrets Manager のシークレットに 'token' キーがありません: {data}"
        )

    # base64→バイナリ→pickle で Credentials を取り出す
    token_b64 = data["token"]
    token_bin = base64.b64decode(token_b64)
    creds = pickle.loads(token_bin)

    # もし期限切れならリフレッシュ
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # リフレッシュ後のアクセストークンを再保存する例:
        updated_token_bin = pickle.dumps(creds)
        updated_token_b64 = base64.b64encode(updated_token_bin).decode("utf-8")
        data["token"] = updated_token_b64
        client.put_secret_value(SecretId=secret_name, SecretString=json.dumps(data))

    return creds


def determine_time_range(timezone="Asia/Tokyo"):
    """
    現在の時刻が 0:00～18:00 なら「今日の今～今日の23:59:59」、
    18:00～24:00 なら「明日の0:00:00～明日の23:59:59」 を返す。

    戻り値: (start_dt, end_dt) タイムゾーン付き datetime
    """
    local_tz = pytz.timezone(timezone)
    now_local = dt.now(local_tz)

    if now_local.hour < 18:
        # 今日の今から今日の23:59:59 まで
        start_dt = now_local
        end_dt = local_tz.localize(
            datetime.datetime.combine(now_local.date(), datetime.time(23, 59, 59))
        )
    else:
        # 明日の0:00:00 から 明日の23:59:59 まで
        tomorrow_date = now_local.date() + timedelta(days=1)
        start_dt = local_tz.localize(
            datetime.datetime.combine(tomorrow_date, datetime.time(0, 0, 0))
        )
        end_dt = local_tz.localize(
            datetime.datetime.combine(tomorrow_date, datetime.time(23, 59, 59))
        )

    return (start_dt, end_dt)


def is_online_event(event):
    """
    イベントがオンラインかどうかを判定:
    - event['conferenceData'] があればオンライン
    - または description に "meet" や "zoom" が含まれる場合もオンライン
    """
    # 1. conferenceData がある場合
    if "conferenceData" in event:
        return True

    # 2. description 中に "meet" or "zoom" があればオンラインとみなす
    desc = event.get("description", "")
    desc_lower = desc.lower()
    if "meet" in desc_lower or "zoom" in desc_lower:
        return True

    return False


def calculate_alarm_times(start_time_local, is_online):
    """
    オンラインなら開始10分前
    それ以外(オフライン)なら80分前
    """
    if is_online:
        alarm_time = start_time_local - timedelta(minutes=10)
        return alarm_time.isoformat()
    else:
        alarm_time = start_time_local - timedelta(minutes=80)
        return alarm_time.isoformat()


def get_orange_events(creds, timezone="Asia/Tokyo"):
    """
    カレンダーAPIで、オレンジ色(colorId=6)かつ「時間あり(dateTime)」のイベントを取得し、
    オンライン/オフラインでアラーム時刻(10分前 or 80分前)を計算して返す。
    """
    local_tz = pytz.timezone(timezone)
    start_dt, end_dt = determine_time_range(timezone=timezone)

    service = build("calendar", "v3", credentials=creds)

    time_min = start_dt.isoformat()
    time_max = end_dt.isoformat()
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

    results = []
    for ev in events:
        # colorId が '6' で、start.dateTime がある(終日でない)イベント
        if ev.get("colorId") == "6" and "dateTime" in ev["start"]:
            summary = ev.get("summary", "（無題）")
            start_time_str = ev["start"]["dateTime"]  # ISO8601
            start_time = dt.fromisoformat(start_time_str).astimezone(local_tz)

            online = is_online_event(ev)
            alarm_time = calculate_alarm_times(start_time, online)

            results.append(
                {
                    "summary": summary,
                    "alarm_time": alarm_time,
                }
            )

    return results


def lambda_handler(event, context):
    """
    AWS Lambda のハンドラ
    """
    # dotenv を読み込む場合（ローカルテストで使いたいなら）
    load_dotenv()

    # 環境変数から Secrets Manager の情報を取得
    secret_name = os.getenv("CALENDAR_TOKEN_SECRET_NAME", "my_calendar_token")
    region_name = os.getenv("AWS_REGION", "ap-northeast-1")
    timezone = os.getenv("TIMEZONE", "Asia/Tokyo")

    # Secrets Manager から token.json 相当を読み込み、Credentials を復元
    creds = load_credentials_from_secrets_manager(secret_name, region_name)

    # オレンジ色イベントを取得
    orange_events = get_orange_events(creds, timezone=timezone)

    # デバッグ用ログ出力
    print(f"Found {len(orange_events)} orange events in the specified range.")
    for ev in orange_events:
        print(f"- {ev['summary']} @ {ev['start_time']}")
        print(f"  alarm_times = {ev['alarm_times']}")

    # 返り値を JSON として返す例
    return json.dumps(orange_events, ensure_ascii=False)


# ローカル実行テスト用
if __name__ == "__main__":
    res = lambda_handler({}, {})
    print("Result:", res)
