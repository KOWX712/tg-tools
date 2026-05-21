#!/usr/bin/env python3

import json
import os
import threading

import requests

COMMAND = "send_to"
HELP = "Send a message to connected channel"

API_BASE = "https://api.telegram.org/bot"

_pending = {}
_lock = threading.Lock()

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
CHAT_FILE = os.path.join(_PROJECT_ROOT, "chat.json")


def _api(method, token, data):
    url = f"{API_BASE}{token}/{method}"
    try:
        r = requests.post(url, json=data, timeout=10)
        result = r.json()
        if not result.get("ok"):
            print(f"[send_to] API {method} failed: {result}", flush=True)
        return result
    except Exception as e:
        print(f"[send_to] API {method} error: {e}", flush=True)
        return None


def _load_chats():
    if not os.path.exists(CHAT_FILE):
        return {"chats": []}
    try:
        with open(CHAT_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"[send_to] Failed to load chat.json: {e}", flush=True)
        return {"chats": []}


def run(message, bot_token):
    chat_id = message["chat"]["id"]

    reply = message.get("reply_to_message")
    if not reply:
        _api("sendMessage", bot_token, {
            "chat_id": chat_id,
            "text": "Reply to a message with /send_to",
        })
        return ""

    data = _load_chats()
    if not data["chats"]:
        _api("sendMessage", bot_token, {
            "chat_id": chat_id,
            "text": "No connected chats. Use /connect first.",
        })
        return ""

    with _lock:
        pending = {
            "reply_chat_id": chat_id,
            "reply_message_id": reply["message_id"],
        }
        if "reply_markup" in reply:
            pending["reply_markup"] = reply["reply_markup"]
        _pending[chat_id] = pending

    keyboard = [[{"text": c["name"], "callback_data": f"send_to:{c['id']}"}]
                for c in data["chats"]]
    keyboard.append([{"text": "Cancel", "callback_data": "send_to:cancel"}])

    _api("sendMessage", bot_token, {
        "chat_id": chat_id,
        "text": "Select a channel or group to send to:",
        "reply_markup": {"inline_keyboard": keyboard},
    })
    return ""


def handle_callback(callback_query, bot_token):
    data = callback_query.get("data", "")
    msg = callback_query.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")
    cb_id = callback_query["id"]

    if data == "send_to:cancel":
        with _lock:
            _pending.pop(chat_id, None)
        _api("editMessageText", bot_token, {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": "Cancelled.",
        })
        _api("answerCallbackQuery", bot_token, {
            "callback_query_id": cb_id,
        })
        return

    if data.startswith("send_to:"):
        target_id_str = data.split(":", 1)[1]
        try:
            target_id = int(target_id_str)
        except ValueError:
            _api("answerCallbackQuery", bot_token, {
                "callback_query_id": cb_id,
                "text": "Invalid target",
                "show_alert": True,
            })
            return

        with _lock:
            pending = _pending.pop(chat_id, None)

        if not pending:
            _api("answerCallbackQuery", bot_token, {
                "callback_query_id": cb_id,
                "text": "Session expired. Try /send_to again.",
                "show_alert": True,
            })
            return

        copy_payload = {
            "chat_id": target_id,
            "from_chat_id": pending["reply_chat_id"],
            "message_id": pending["reply_message_id"],
        }
        chats_data = _load_chats()
        for c in chats_data["chats"]:
            if c["id"] == target_id and c.get("message_thread_id"):
                copy_payload["message_thread_id"] = c["message_thread_id"]
                break

        result = _api("copyMessage", bot_token, copy_payload)

        if result and result.get("ok"):
            # copyMessage drops reply_markup; re-attach it if the source had one
            if "reply_markup" in pending:
                sent_msg_id = result["result"]["message_id"]
                _api("editMessageReplyMarkup", bot_token, {
                    "chat_id": target_id,
                    "message_id": sent_msg_id,
                    "reply_markup": pending["reply_markup"],
                })
            _api("editMessageText", bot_token, {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": "Sent! ✅",
            })
        else:
            _api("editMessageText", bot_token, {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": (
                    "Failed to send. Make sure the bot is a member "
                    "of the target chat."
                ),
            })

        _api("answerCallbackQuery", bot_token, {
            "callback_query_id": cb_id,
        })
