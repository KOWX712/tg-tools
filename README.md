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
- **Custom Commands**: Drop Python modules into `command/` to add slash commands (e.g., `/hello`). The daemon auto-discovers and registers them with Telegram on startup.
- **Security**: Only listens to messages from your authorized `CHAT_ID` (set in `.env`).

### Usage & Service Management

| Command | Action |
| :--- | :--- |
| `python3 tgd.py run`      | Run the daemon manually in the current terminal |
| `python3 tgd.py install`  | Install script to PATH (symlink or shell rc) |
| `python3 tgd.py start`    | Enable and start the systemd service (implies `install`) |
| `python3 tgd.py stop`     | Stop the background service |
| `python3 tgd.py restart`  | Restart the background service |
| `python3 tgd.py status`   | Show current status of the service |
| `python3 tgd.py logs`     | View live logs (follow output) |
| `python3 tgd.py uninstall`| Remove from PATH and disable the systemd service |

### Troubleshooting
If the clipboard functionality fails when running as a service, ensure systemd has access to your Wayland/X11 session:
```bash
systemctl --user import-environment WAYLAND_DISPLAY XDG_RUNTIME_DIR DISPLAY
```

The systemd service uses `KillMode=process` so child processes (e.g. tmux sessions) are **not** killed when the service restarts or stops.

### Custom Commands

Drop a `.py` file into the `command/` directory, or a subdirectory with a matching `.py` file. The daemon auto-discovers all modules on startup, loads them, and registers them with Telegram via `setMyCommands`.

| Layout | Command | Example |
|--------|---------|---------|
| `command/hello.py` | `/hello` | Flat file |
| `command/tmux/tmux.py` | `/tmux` | One-level subdirectory |

#### Module Interface

| Attribute | Description |
| :--- | :--- |
| `COMMAND` | The slash command name (e.g. `"hello"` for `/hello`) |
| `HELP` | Short description shown in Telegram's command list |
| `run(message, bot_token)` | Handler — receives the message dict and bot token, returns reply text |
| `handle_callback(callback_query, bot_token)` | _Optional._ Handles inline keyboard button presses |

#### Demo module (`command/hello.py`)
```python
COMMAND = "hello"
HELP = "Send a greeting"

def run(message: dict, bot_token: str) -> str:
    return "hi"
```

---

## 2. Telegram Sender (`tgsend.py`)

A simple CLI tool to send files or text to your Telegram chat.

### Usage
```bash
python3 tgsend.py <file1|text1> [file2|text2] ...
```

| Command | Action |
| :--- | :--- |
| `python3 tgsend.py install`            | Install script to PATH (symlink or shell rc) |
| `python3 tgsend.py install-service kde`| Install the KDE Dolphin right-click menu |
| `python3 tgsend.py uninstall`          | Remove from PATH and uninstall KDE service menu |

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
