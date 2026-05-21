## Send To Command (`/send_to`)

Forwards replied message to a connected channel or group from `chat.json`.

### Usage

1. Reply to a message with `/send_to`
2. Bot shows inline buttons for each connected chat
3. Tap a chat to send — or **Cancel** to abort

### Prerequisites

- At least one chat must be connected via `/connect` first
- The bot must be a member of the target channel/group

### Notes

- Uses `copyMessage` to send the content (no "Forwarded from" header)
- Supports any message type (text, photo, document, video, etc.)
- Session state expires after the first interaction
