#!/usr/bin/env python3

import json
import os
import threading
from datetime import datetime, timezone

import requests

COMMAND = "connect"
HELP = "Connect to a channel or group"

API_BASE = "https://api.telegram.org/bot"

_pending = set()
_pending_thread = {}
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
            print(f"[connect] API {method} failed: {result}", flush=True)
        return result
    except Exception as e:
        print(f"[connect] API {method} error: {e}", flush=True)
        return None


def _load_chats():
    if not os.path.exists(CHAT_FILE):
        return {"chats": []}
    try:
        with open(CHAT_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"[connect] Failed to load chat.json: {e}", flush=True)
        return {"chats": []}


def _save_chats(data):
    try:
        with open(CHAT_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[connect] Failed to save chat.json: {e}", flush=True)
        return False


def _cancel_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Cancel",
                    "callback_data": "connect:cancel",
                }
            ]
        ]
    }


def _management_keyboard():
    data = _load_chats()
    keyboard = []
    for c in data["chats"]:
        name = c.get("name", f"Chat {c['id']}")
        keyboard.append([
            {"text": f"✕ {name}", "callback_data": f"connect:remove:{c['id']}"}
        ])
    keyboard.append([{"text": "Add new", "callback_data": "connect:add"}])
    keyboard.append([{"text": "Cancel", "callback_data": "connect:cancel"}])
    return {"inline_keyboard": keyboard}


def run(message, bot_token):
    """Handles /connect — shows management UI or forward prompt."""
    chat_id = message["chat"]["id"]
    data = _load_chats()

    if data["chats"]:
        _api("sendMessage", bot_token, {
            "chat_id": chat_id,
            "text": "Connected chats:",
            "reply_markup": _management_keyboard(),
        })
    else:
        with _lock:
            _pending.add(chat_id)
        _api("sendMessage", bot_token, {
            "chat_id": chat_id,
            "text": "Forward a message from a channel or group",
            "reply_markup": _cancel_keyboard(),
        })
    return ""


def handle_callback(callback_query, bot_token):
    """Handles Cancel, Add, Remove, and Set Thread button presses."""
    data = callback_query.get("data", "")
    msg = callback_query.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")
    cb_id = callback_query["id"]

    parts = data.split(":", 2)
    if len(parts) < 2 or parts[0] != "connect":
        return

    action = parts[1]

    if action == "cancel":
        with _lock:
            _pending.discard(chat_id)
            _pending_thread.pop(chat_id, None)
        _api("editMessageText", bot_token, {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": "Cancelled.",
        })

    elif action == "add":
        with _lock:
            _pending.add(chat_id)
        _api("editMessageText", bot_token, {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": "Forward a message from a channel or group",
            "reply_markup": _cancel_keyboard(),
        })

    elif action == "remove":
        target_id = int(parts[2])
        data = _load_chats()
        name = ""
        for c in data["chats"]:
            if c["id"] == target_id:
                name = c.get("name", f"Chat {target_id}")
                break
        _api("editMessageText", bot_token, {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": f"Remove <b>{name}</b>?",
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "Yes", "callback_data": f"connect:confirm_remove:{target_id}"},
                        {"text": "No", "callback_data": "connect:cancel_remove"},
                    ]
                ]
            },
        })

    elif action == "confirm_remove":
        target_id = int(parts[2])
        data = _load_chats()
        data["chats"] = [c for c in data["chats"] if c["id"] != target_id]
        _save_chats(data)
        _api("editMessageText", bot_token, {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": "Removed.",
        })

    elif action == "cancel_remove":
        _api("editMessageText", bot_token, {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": "Connected chats:",
            "reply_markup": _management_keyboard(),
        })

    elif action == "set_thread":
        target_id = int(parts[2])
        with _lock:
            _pending_thread[chat_id] = target_id
        _api("editMessageText", bot_token, {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": "Send the numeric thread/topic ID for this chat.\nOr /cancel to abort.",
        })

    _api("answerCallbackQuery", bot_token, {
        "callback_query_id": cb_id,
    })


def _extract_source_chat(message):
    """Extract the source chat from a forwarded message.

    Tries forward_from_chat first (channels, supergroups),
    then falls back to forward_origin for group forwards.
    Returns (chat_id, chat_name, chat_type) or (None, None, None).
    """
    forward_chat = message.get("forward_from_chat")
    if not forward_chat:
        forward_origin = message.get("forward_origin")
        if forward_origin:
            otype = forward_origin.get("type")
            if otype == "chat":
                forward_chat = forward_origin.get("sender_chat")
            elif otype == "channel":
                forward_chat = forward_origin.get("chat")

    if not forward_chat:
        return None, None, None

    chat_id = forward_chat["id"]
    chat_name = (
        forward_chat.get("title")
        or forward_chat.get("username")
        or f"Chat {chat_id}"
    )
    chat_type = forward_chat.get("type", "unknown")
    return chat_id, chat_name, chat_type


def handle_forwarded(message, bot_token):
    """Extract chat info from a forwarded message and save to chat.json.

    Returns True if the message was consumed (pending connect was active),
    False otherwise.
    """
    chat_id = message["chat"]["id"]

    with _lock:
        if chat_id not in _pending:
            return False
        _pending.discard(chat_id)

    target_id, target_name, target_type = _extract_source_chat(message)
    if not target_id:
        _api("sendMessage", bot_token, {
            "chat_id": chat_id,
            "text": (
                "That doesn't look like a forwarded message from a "
                "channel or group. Send /connect to try again."
            ),
        })
        return True

    if target_type not in ("channel", "group", "supergroup"):
        _api("sendMessage", bot_token, {
            "chat_id": chat_id,
            "text": (
                f"Unsupported chat type: <b>{target_type}</b>. "
                "Please forward a message from a channel or group."
            ),
            "parse_mode": "HTML",
        })
        return True

    data = _load_chats()
    existing = None
    for c in data["chats"]:
        if c["id"] == target_id:
            existing = c
            break

    if existing:
        existing["name"] = target_name
        existing["type"] = target_type
    else:
        entry = {
            "id": target_id,
            "name": target_name,
            "type": target_type,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        if target_type == "supergroup":
            entry["message_thread_id"] = None
        data["chats"].append(entry)

    if _save_chats(data):
        payload = {
            "chat_id": chat_id,
            "text": f"Connected to <b>{target_name}</b> ({target_type})",
            "parse_mode": "HTML",
        }
        if target_type == "supergroup":
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": "Set Thread ID", "callback_data": f"connect:set_thread:{target_id}"}]
                ]
            }
        _api("sendMessage", bot_token, payload)
    else:
        _api("sendMessage", bot_token, {
            "chat_id": chat_id,
            "text": "Failed to save chat info. Check logs.",
        })

    return True


def handle_plain_text(message, bot_token):
    """Handles plain text input for thread ID setting."""
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    with _lock:
        target_id = _pending_thread.pop(chat_id, None)

    if not target_id:
        return False

    if text.lower() == "/cancel":
        _api("sendMessage", bot_token, {
            "chat_id": chat_id,
            "text": "Cancelled.",
        })
        return True

    try:
        thread_id = int(text)
    except ValueError:
        _api("sendMessage", bot_token, {
            "chat_id": chat_id,
            "text": "Invalid thread ID. Send a number or /cancel.",
        })
        return True

    data = _load_chats()
    for c in data["chats"]:
        if c["id"] == target_id:
            c["message_thread_id"] = thread_id
            break
    _save_chats(data)

    _api("sendMessage", bot_token, {
        "chat_id": chat_id,
        "text": f"Thread ID set to {thread_id}.",
    })
    return True
