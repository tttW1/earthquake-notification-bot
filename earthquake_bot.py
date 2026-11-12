import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

FEED_URL = "https://www.data.jma.go.jp/developer/xml/feed/eqvol.xml"
ALLOWED_PREFIX = "https://www.data.jma.go.jp/"
ATOM = {"atom": "http://www.w3.org/2005/Atom"}
TARGET_TITLES = ("震度速報", "震源に関する情報", "震源・震度に関する情報")
INTENSITY = {
    "1": "1", "2": "2", "3": "3", "4": "4",
    "5-": "5弱", "5+": "5強", "6-": "6弱", "6+": "6強", "7": "7",
}
TIMEOUT = 20
USER_AGENT = "earthquake-notification-bot/1.0"


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return res.read()


def get_earthquake_entries():
    """フィードから地震関連の電文を新しい順に返す。"""
    root = ET.fromstring(http_get(FEED_URL))
    entries = []
    for e in root.findall("atom:entry", ATOM):
        title = e.findtext("atom:title", default="", namespaces=ATOM)
        if not any(t in title for t in TARGET_TITLES):
            continue
        link = e.find("atom:link", ATOM)
        entries.append(
            {
                "title": title,
                "updated": e.findtext("atom:updated", default="", namespaces=ATOM),
                "link": link.get("href", "") if link is not None else "",
            }
        )
    entries.sort(key=lambda x: x["updated"], reverse=True)
    return entries


def strip_namespaces(root):
    """タグ名から名前空間を取り除き、検索しやすくする。"""
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]


def parse_report(xml_bytes):
    """電文XMLから必要な項目を取り出す。無い項目は空文字にする。"""
    root = ET.fromstring(xml_bytes)
    strip_namespaces(root)

    def text(path):
        value = root.findtext(path)
        return value.strip() if value else ""

    magnitude = ""
    mag = root.find("Body/Earthquake/Magnitude")
    if mag is not None:
        magnitude = (mag.get("description") or mag.text or "").strip()

    depth = ""
    coord = root.find("Body/Earthquake/Hypocenter/Area/Coordinate")
    if coord is not None:
        m = re.search(r"深さ\s*(.+)$", coord.get("description", ""))
        if m:
            depth = m.group(1).strip()

    max_int = text("Body/Intensity/Observation/MaxInt")
    return {
        "info_type": text("Head/InfoType"),
        "headline": text("Head/Headline/Text"),
        "origin": text("Body/Earthquake/OriginTime"),
        "place": text("Body/Earthquake/Hypocenter/Area/Name"),
        "magnitude": magnitude,
        "depth": depth,
        "max_int": INTENSITY.get(max_int, max_int),
    }


def format_time(value):
    try:
        return datetime.fromisoformat(value).strftime("%Y年%m月%d日 %H:%M頃")
    except ValueError:
        return value


def build_message(title, info):
    lines = [f"【地震情報】{title}"]
    if info["info_type"] and info["info_type"] != "発表":
        lines.append(f"種別：{info['info_type']}")
    if info["origin"]:
        lines.append(f"発生時刻：{format_time(info['origin'])}")
    if info["place"]:
        lines.append(f"震源地：{info['place']}")
    if info["magnitude"]:
        lines.append(f"規模：{info['magnitude']}")
    if info["depth"]:
        lines.append(f"深さ：{info['depth']}")
    if info["max_int"]:
        lines.append(f"最大震度：{info['max_int']}")
    if info["headline"]:
        lines.append("")
        lines.append(info["headline"])
    lines.append("")
    lines.append("出典：気象庁")
    return "\n".join(lines)


def send_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN または TELEGRAM_CHAT_ID が設定されていません。")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return res.status == 200
    except urllib.error.HTTPError as e:
        # トークンがURLに含まれるため、URLは表示しない
        print(f"Telegramがエラーを返しました: {e.code}")
    except urllib.error.URLError:
        print("Telegramに接続できませんでした。")
    return False


def main():
    try:
        entries = get_earthquake_entries()
        if not entries:
            print("フィードに対象の地震情報がありません。")
            return 0

        latest = entries[0]
        if not latest["link"].startswith(ALLOWED_PREFIX):
            print("想定外のURLのため中止しました。")
            return 1

        info = parse_report(http_get(latest["link"]))
    except urllib.error.HTTPError as e:
        print(f"気象庁がエラーを返しました: {e.code}")
        return 1
    except urllib.error.URLError:
        print("気象庁に接続できませんでした。")
        return 1
    except ET.ParseError:
        print("XMLの解析に失敗しました。")
        return 1

    message = build_message(latest["title"], info)
    print(message)
    ok = send_telegram(message)
    print("送信成功" if ok else "送信失敗")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
