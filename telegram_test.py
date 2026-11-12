import json
import os
import sys
import urllib.error
import urllib.request


def send_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN または TELEGRAM_CHAT_ID が設定されていません。")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.status == 200
    except urllib.error.HTTPError as e:
        # トークンがURLに含まれるため、詳細なURLは表示しない
        print(f"Telegramがエラーを返しました: {e.code}")
    except urllib.error.URLError:
        print("Telegramに接続できませんでした。")
    return False


if __name__ == "__main__":
    ok = send_telegram("テスト送信：地震通知Botの接続確認です。")
    print("送信成功" if ok else "送信失敗")
    sys.exit(0 if ok else 1)
