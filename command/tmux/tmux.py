#!/usr/bin/env python3

import os
import subprocess
import shutil
import requests

COMMAND = "tmux"
HELP = "Manage tmux sessions"

API_BASE = "https://api.telegram.org/bot"

TITLE = "<b>Tmux Manager</b>\n\n"
MESSAGE = {
    "main": TITLE + "Manage your tmux sessions",
    "not_installed": TITLE + "tmux is not installed on this system",
    "start": TITLE + "Started a new tmux session",
    "stop": TITLE + "Stopped all tmux sessions",
    "stop_fail": TITLE + "No tmux sessions to stop",
    "list": TITLE + "Active tmux sessions",
    "list_empty": TITLE + "No active tmux sessions",
}


def _api(method, token, data):
    url = f"{API_BASE}{token}/{method}"
    try:
        return requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"Telegram API error: {e}", flush=True)
        return None


def _menu_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Start",
                    "callback_data": "tmux:start",
                    "style": "success"
                },
                {
                    "text": "Stop",
                    "callback_data": "tmux:stop",
                    "style": "danger"
                }
            ],
            [
                {
                    "text": "List",
                    "callback_data": "tmux:list:menu",
                    "style": "primary"
                }
            ],
        ]
    }


def _started_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Stop",
                    "callback_data": "tmux:stop",
                    "style": "danger"
                }
            ],
            [
                {
                    "text": "List",
                    "callback_data": "tmux:list:started",
                    "style": "primary"
                }
            ],
        ]
    }


def _stopped_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "List",
                    "callback_data": "tmux:list:stopped",
                    "style": "primary"
                }
            ],
        ]
    }


def _back_keyboard(origin):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "←  Back",
                    "callback_data": f"tmux:back:{origin}",
                    "style": "primary"
                }
            ],
        ]
    }


def run(message, bot_token):
    """Handles /tmux — show interactive menu with buttons."""
    chat_id = message["chat"]["id"]

    if not shutil.which("tmux"):
        _api("sendMessage", bot_token, {
            "chat_id": chat_id,
            "text": MESSAGE["not_installed"],
        })
        return ""

    _api("sendMessage", bot_token, {
        "chat_id": chat_id,
        "text": MESSAGE["main"],
        "parse_mode": "HTML",
        "reply_markup": _menu_keyboard(),
    })
    return ""


def handle_callback(callback_query, bot_token):
    """Handles button clicks from the tmux menu."""
    data = callback_query.get("data", "")
    msg = callback_query.get("message", {})
    chat_id = msg["chat"]["id"]
    message_id = msg["message_id"]
    cb_id = callback_query["id"]

    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    origin = parts[2] if len(parts) > 2 else "menu"

    text = ""
    keyboard = None

    if action == "start":
        r_check = subprocess.run(
            ["tmux", "list-sessions"],
            capture_output=True, text=True, timeout=5,
        )
        if r_check.returncode == 0:
            text = f"{TITLE}A tmux session is already running.\n\n{r_check.stdout.strip()}"
            keyboard = _started_keyboard()
        else:
            r = subprocess.run(
                ["tmux", "new-session", "-d"],
                capture_output=True, text=True, timeout=5,
                cwd=os.path.expanduser("~"),
            )
            text = MESSAGE["start"] if r.returncode == 0 \
                else f"{TITLE}Failed to start a new tmux session: {r.stderr.strip()}"
            keyboard = _started_keyboard()

    elif action == "stop":
        r = subprocess.run(
            ["tmux", "kill-server"],
            capture_output=True, text=True, timeout=5,
        )
        text = MESSAGE["stop"] if r.returncode == 0 \
            else MESSAGE["stop_fail"]
        keyboard = _stopped_keyboard()

    elif action == "list":
        r = subprocess.run(
            ["tmux", "list-sessions"],
            capture_output=True, text=True, timeout=5,
        )
        text = r.stdout.strip() if r.returncode == 0 else MESSAGE["list_empty"]
        keyboard = _back_keyboard(origin)

    elif action in ("back", "menu"):
        if origin == "menu":
            text = MESSAGE["main"]
            keyboard = _menu_keyboard()
        elif origin == "started":
            text = MESSAGE["start"]
            keyboard = _started_keyboard()
        elif origin == "stopped":
            text = MESSAGE["stop"]
            keyboard = _stopped_keyboard()

    if text:
        _api("editMessageText", bot_token, {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": keyboard,
        })

    _api("answerCallbackQuery", bot_token, {
        "callback_query_id": cb_id,
    })
