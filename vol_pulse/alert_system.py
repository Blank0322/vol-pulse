from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class AlertMessage:
    title: str
    body: str


class AlertSystem:
    def __init__(self) -> None:
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
        self.pushover_user_key = os.getenv("PUSH_USER_KEY")
        self.pushover_api_token = os.getenv("PUSH_API_TOKEN")
        self.pushover_repeat = int(os.getenv("PUSH_REPEAT", "1"))
        self.pushover_interval = float(os.getenv("PUSH_INTERVAL_SEC", "1.2"))
        self.pushover_title_prefix = os.getenv("PUSH_TITLE_PREFIX", "!!!")

    def send(self, message: AlertMessage) -> None:
        payload = f"{message.title}\n{message.body}"
        sent = False
        if self.telegram_token and self.telegram_chat_id:
            sent |= self._send_telegram(payload)
        if self.discord_webhook:
            sent |= self._send_discord(payload)
        if self.pushover_user_key and self.pushover_api_token:
            sent |= self._send_pushover(message)
        if not sent:
            print(payload)

    def _send_telegram(self, text: str) -> bool:
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        data = {"chat_id": self.telegram_chat_id, "text": text}
        try:
            resp = requests.post(url, data=data, timeout=10)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def _send_discord(self, text: str) -> bool:
        try:
            resp = requests.post(
                self.discord_webhook,
                data=json.dumps({"content": text}),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            return 200 <= resp.status_code < 300
        except requests.RequestException:
            return False

    def _send_pushover(self, message: AlertMessage) -> bool:
        url = "https://api.pushover.net/1/messages.json"
        try:
            ok = True
            repeats = max(self.pushover_repeat, 1)
            for i in range(repeats):
                data = {
                    "token": self.pushover_api_token,
                    "user": self.pushover_user_key,
                    "title": (
                        f"{self.pushover_title_prefix} {message.title} ({i+1})"
                        if repeats > 1
                        else message.title
                    ),
                    "message": message.body,
                    "sound": "vibrate",
                    "priority": 1,
                }
                resp = requests.post(url, data=data, timeout=10)
                if os.getenv("PUSH_DEBUG", "").strip():
                    print(f"Pushover status: {resp.status_code} {resp.text}")
                ok = ok and (200 <= resp.status_code < 300)
                if i < repeats - 1:
                    time.sleep(self.pushover_interval)
            return ok
        except requests.RequestException:
            return False
