## Connect Command (`/connect`)

Saves a channel or group chat ID to `chat.json` for future use (e.g., sending messages via other commands).

### Usage

1. Send `/connect` — bot replies "Forward a message from a channel or group" with a **Cancel** button
2. Forward any message from the target channel or group to the bot (just the message, no need to reply)
3. Bot saves the chat ID and name to `chat.json` in the project root and confirms success

### Chat JSON Format

```json
{
  "chats": [
    {
      "id": -1001234567890,
      "name": "My Channel",
      "type": "channel",
      "added_at": "2026-05-21T12:00:00+00:00"
    }
  ]
}
```

### Notes

- **Cancel** button clears the pending state without saving
- Supports channels (`channel`), basic groups (`group`), and supergroups (`supergroup`)
- Group forwards use Telegram's `forward_origin` field (Bot API 7.0+) as fallback when `forward_from_chat` is not available
- If the same chat is forwarded again, its entry is updated (not duplicated)
