# Telegram Tools

A collection of simple scripts to interact with Telegram via a bot.

> [!WARNING]
> Personal tool, no warranty.

## 1. Telegram Daemon (`tgd.py`)

A background listener that monitors your Telegram chat and performs automated actions.

### Features
- **Receive Files**: Automatically downloads any document, photo, or video sent to the bot directly to your `~/Downloads` folder.
- **Auto-Clipboard**: Any text message sent to the bot is automatically copied to your system clipboard.
  - Supports `wl-copy` (Wayland), `xclip` (X11), and `xsel` (X11).
- **Security**: Only listens to messages from your authorized `CHAT_ID` (set in `.env`).

### Usage & Service Management
The `tgd.py` script now acts as its own service manager:

| Command | Action |
| :--- | :--- |
| `python3 tgd.py start` | Install, enable, and start the background service |
| `python3 tgd.py stop` | Stop the background service |
| `python3 tgd.py restart` | Restart the background service |
| `python3 tgd.py status` | Show current status of the service |
| `python3 tgd.py logs` | View live logs (follow output) |
| `python3 tgd.py uninstall` | Disable and stop the service |
| `python3 tgd.py run` | Run the daemon manually in the current terminal |

### Troubleshooting
If the clipboard functionality fails when running as a service, ensure systemd has access to your Wayland/X11 session:
```bash
systemctl --user import-environment WAYLAND_DISPLAY XDG_RUNTIME_DIR DISPLAY
```

---

## 2. Telegram Sender (`tgsend.py`)

A simple CLI tool to send files to your Telegram chat.

### Usage
```bash
python3 tgsend.py <file1> [file2] ...
```

### KDE Service Menu Integration

- A right-click "Service Menu" for Dolphin allows you to send files directly from your file manager.

| Command | Action |
| :--- | :--- |
| `python3 tgsend.py install-service kde` | Install the KDE right-click menu |
| `python3 tgsend.py uninstall`           | Remove installed service |

---

## Configuration (`.env`)
Both scripts require a `.env` file in the same directory:
```env
BOT_TOKEN="your_bot_token_here"
CHAT_ID=your_numeric_chat_id
```

## Requirements
- `python3`
- `pip install requests python-dotenv`
- A clipboard tool (`wl-clipboard`, `xclip`, or `xsel`)
