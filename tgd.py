#!/usr/bin/env python3

import os
import sys
import time
import requests
import subprocess
import shutil
import signal
import threading
import importlib.util
from dotenv import load_dotenv

# Load environment variables
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DOWNLOAD_DIR = os.path.expanduser("~/Downloads")

def send_notification(message, urgency="normal", icon="telegram", action_path=None):
    """Sends a desktop notification using notify-send."""
    if shutil.which("notify-send"):
        try:
            cmd = ["notify-send", "-u", urgency, "-i", icon, "Telegram Tool", message]

            if action_path and os.path.exists(action_path):
                if os.path.isfile(action_path):
                    action_path = os.path.dirname(action_path)

                cmd.extend(["--action=open=Open"])

                def handle_action():
                    try:
                        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
                        stdout, _ = proc.communicate()
                        if "open" in stdout.strip():
                            if shutil.which("xdg-open"):
                                subprocess.run(["xdg-open", action_path], check=False)
                    except Exception as e:
                        print(f"Error handling notification action: {e}")

                threading.Thread(target=handle_action, daemon=True).start()
            else:
                subprocess.run(cmd, check=False)
        except Exception as e:
            print(f"Failed to send notification: {e}")


def get_clipboard_tool():
    """Finds available clipboard tool."""
    for tool in ['wl-copy', 'xclip', 'xsel']:
        if subprocess.run(['which', tool], capture_output=True).returncode == 0:
            return tool
    return None


def copy_to_clipboard(text):
    """Copies text to clipboard using available tool."""
    tool = get_clipboard_tool()
    if not tool:
        print("No clipboard tool found (wl-copy, xclip, xsel).")
        return False

    try:
        if tool == 'wl-copy':
            subprocess.run(['wl-copy'], input=text.encode(), check=True)
        elif tool == 'xclip':
            subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode(), check=True)
        elif tool == 'xsel':
            subprocess.run(['xsel', '--clipboard', '--input'], input=text.encode(), check=True)

        print(f"Copied to clipboard using {tool}: {text[:50]}...")
        send_notification(f"Copied to clipboard: {text[:50]}...")
        return True
    except Exception as e:
        msg = f"Failed to copy to clipboard: {e}"
        print(msg)
        send_notification(msg, urgency="critical")
        return False


def react_to_message(chat_id, message_id, emoji="👍"):
    """Reacts to a message with an emoji."""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMessageReaction"
        data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'reaction': [{'type': 'emoji', 'emoji': emoji}]
        }
        response = requests.post(url, json=data, timeout=10).json()
        if not response.get('ok'):
            print(f"Failed to react to message with {emoji}: {response}", flush=True)
        else:
            print(f"Reacted to message {message_id} with {emoji}", flush=True)

    except Exception as e:
        print(f"Error reacting to message: {e}", flush=True)


COMMANDS = {}


def send_reply(chat_id, text):
    """Sends a reply text message to a Telegram chat."""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {'chat_id': chat_id, 'text': text}
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending reply: {e}", flush=True)
        return False


def load_commands():
    """Dynamically loads all command modules from the command/ directory."""
    global COMMANDS
    command_dir = os.path.join(SCRIPT_DIR, "command")
    if not os.path.isdir(command_dir):
        return

    for entry in sorted(os.listdir(command_dir)):
        if entry.startswith("_"):
            continue
        module_name = None
        module_path = None

        if entry.endswith(".py"):
            # Flat file: command/hello.py → /hello
            module_name = entry[:-3]
            module_path = os.path.join(command_dir, entry)
        else:
            # One-level subdirectory: command/tmux/tmux.py → /tmux
            subdir = os.path.join(command_dir, entry)
            if os.path.isdir(subdir):
                nested = os.path.join(subdir, f"{entry}.py")
                if os.path.isfile(nested):
                    module_name = entry
                    module_path = nested

        if module_name is None or module_path is None:
            continue

        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "run"):
                COMMANDS[module_name] = module
                print(f"Loaded command: /{module_name}", flush=True)
        except Exception as e:
            print(f"Failed to load command '{module_name}': {e}", flush=True)


def update_command_list():
    """Registers all loaded commands with Telegram's setMyCommands."""
    if not COMMANDS:
        return

    commands = []
    for name, mod in COMMANDS.items():
        cmd = getattr(mod, "COMMAND", name)
        help_text = getattr(mod, "HELP", "")
        commands.append({"command": cmd, "description": help_text[:128]})

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands"
        response = requests.post(url, json={"commands": commands}, timeout=10).json()
        if response.get("ok"):
            print(f"Registered {len(commands)} command(s) with Telegram", flush=True)
        else:
            print(f"Failed to register commands: {response}", flush=True)
    except Exception as e:
        print(f"Error registering commands: {e}", flush=True)


def process_command(message, text):
    """Routes a command message to the appropriate handler."""
    chat_id = message['chat']['id']
    message_id = message['message_id']

    parts = text.split()
    cmd = parts[0].lstrip("/").split("@")[0].lower()

    if cmd in COMMANDS:
        try:
            response = COMMANDS[cmd].run(message, BOT_TOKEN)
            if response:
                send_reply(chat_id, response)
                react_to_message(chat_id, message_id, "👍")
        except Exception as e:
            print(f"Error executing /{cmd}: {e}", flush=True)
    else:
        send_reply(chat_id, f"Unknown command: /{cmd}")


def process_callback_query(callback_query):
    """Routes a callback query to the appropriate command module."""
    data = callback_query.get("data", "")
    cmd_name = data.split(":", 1)[0] if ":" in data else data

    if cmd_name in COMMANDS:
        mod = COMMANDS[cmd_name]
        if hasattr(mod, "handle_callback"):
            try:
                mod.handle_callback(callback_query, BOT_TOKEN)
            except Exception as e:
                print(f"Error in callback for {cmd_name}: {e}", flush=True)


MIME_EXTENSION_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
    "image/tiff": ".tiff",
    "image/x-icon": ".ico",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
    "video/quicktime": ".mov",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/flac": ".flac",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/gzip": ".gz",
    "application/x-tar": ".tar",
    "application/x-7z-compressed": ".7z",
    "application/json": ".json",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "text/html": ".html",
    "text/xml": ".xml",
}


def _mime_extension(mime_type):
    if not mime_type:
        return None
    return MIME_EXTENSION_MAP.get(mime_type.lower().split(";")[0].strip())


def download_file(file_id, file_name, mime_type=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
        params = {'file_id': file_id}
        response = requests.get(url, params=params, timeout=10).json()

        if not response.get('ok'):
            print(f"Failed to get file info: {response}")
            return False

        file_path = response['result']['file_path']
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        if not file_name:
            file_name = os.path.basename(file_path)

        known_exts = {
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
            ".svg", ".tiff", ".tif", ".ico",
            ".mp4", ".webm", ".mkv", ".mov",
            ".mp3", ".ogg", ".wav", ".flac",
            ".pdf", ".zip", ".gz", ".tar", ".7z",
            ".json", ".txt", ".csv", ".html", ".xml",
        }
        name_part, ext_part = os.path.splitext(file_name)
        current_ext = ext_part.lower() if ext_part else ""

        if mime_type:
            mime_ext = _mime_extension(mime_type)
            if mime_ext and mime_ext != current_ext:
                file_name = f"{name_part}{mime_ext}"
        elif not current_ext or current_ext not in known_exts:
            server_ext = os.path.splitext(os.path.basename(file_path))[1]
            if server_ext:
                file_name = f"{name_part}{server_ext}"

        local_path = os.path.join(DOWNLOAD_DIR, file_name)

        print(f"Downloading {file_name}...")
        file_data = requests.get(download_url, timeout=30).content
        with open(local_path, 'wb') as f:
            f.write(file_data)
        success_msg = f"Saved to {local_path}"
        print(success_msg)
        send_notification(f"Downloaded: {file_name}", action_path=local_path)
        return True

    except Exception as e:
        fail_msg = f"Error downloading file: {e}"
        print(fail_msg)
        send_notification(fail_msg, urgency="critical")
        return False


def process_message(message):
    """Processes an individual message."""
    chat_id = message['chat']['id']
    msg_chat_id = str(chat_id)
    if msg_chat_id != str(CHAT_ID):
        print(f"Ignored message from unauthorized chat: {msg_chat_id}", flush=True)
        return

    message_id = message['message_id']

    if 'document' in message:
        doc = message['document']
        if download_file(doc['file_id'], doc.get('file_name'), doc.get('mime_type')):
            react_to_message(chat_id, message_id, "👍")
    elif 'photo' in message:
        photo = message['photo'][-1]
        if download_file(photo['file_id'], None):
            react_to_message(chat_id, message_id, "👍")
    elif 'video' in message:
        video = message['video']
        if download_file(video['file_id'], video.get('file_name'), video.get('mime_type')):
            react_to_message(chat_id, message_id, "👍")
    elif 'text' in message:
        text = message['text']
        if text.startswith("/"):
            process_command(message, text)
        else:
            handled = False
            if 'forward_from_chat' in message or 'forward_from' in message:
                for name, mod in COMMANDS.items():
                    if hasattr(mod, 'handle_forwarded'):
                        if mod.handle_forwarded(message, BOT_TOKEN):
                            handled = True
                            break
            if not handled:
                for name, mod in COMMANDS.items():
                    if hasattr(mod, 'handle_plain_text'):
                        if mod.handle_plain_text(message, BOT_TOKEN):
                            handled = True
                            break
            if not handled and copy_to_clipboard(text):
                react_to_message(chat_id, message_id, "👍")


def run_daemon():
    """Main loop for the Telegram listener."""
    if not BOT_TOKEN or not CHAT_ID:
        print("Error: BOT_TOKEN or CHAT_ID not set in .env")
        return

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    print(f"Daemon started. Listening for Chat ID: {CHAT_ID}")
    print(f"Downloads will be saved to: {DOWNLOAD_DIR}")
    env_path = os.path.join(SCRIPT_DIR, ".env")
    last_env_mtime = os.path.getmtime(env_path) if os.path.exists(env_path) else 0

    def restart_process():
        print("\n--- Restarting daemon... ---", flush=True)
        sys.stdout.flush()
        sys.stderr.flush()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    signal.signal(signal.SIGHUP, lambda s, f: restart_process())

    load_commands()
    update_command_list()
    offset = 0

    while True:
        if os.path.exists(env_path):
            try:
                current_mtime = os.path.getmtime(env_path)
                if current_mtime > last_env_mtime:
                    print("\n--- .env change detected. ---", flush=True)
                    restart_process()
            except Exception:
                pass

        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {'offset': offset, 'timeout': 30}
            response = requests.get(url, params=params, timeout=35).json()

            if response.get('ok'):
                for update in response['result']:
                    if 'message' in update:
                        process_message(update['message'])
                    elif 'callback_query' in update:
                        process_callback_query(update['callback_query'])
                    offset = update['update_id'] + 1
            else:
                print(f"Error from Telegram: {response}")
                time.sleep(5)
        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nStopping daemon...")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(5)


def generate_service_file():
    """Installs the systemd user service file."""
    python_path = sys.executable
    script_path = os.path.realpath(__file__)
    working_dir = os.path.dirname(script_path)

    service_content = f"""[Unit]
Description=Telegram Download and Clipboard Daemon
After=network.target

[Service]
ExecStart={python_path} {script_path} run
WorkingDirectory={working_dir}
KillMode=process
Environment=PYTHONUNBUFFERED=1
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""

    # Path for user systemd services
    service_dir = os.path.expanduser("~/.config/systemd/user")
    os.makedirs(service_dir, exist_ok=True)
    service_file = os.path.join(service_dir, "tgd.service")

    try:
        # Save to systemd user directory
        with open(service_file, "w") as f:
            f.write(service_content)

        # Also save a copy in the current directory
        local_service_path = os.path.join(working_dir, "tgd.service")
        with open(local_service_path, "w") as f:
            f.write(service_content)

        print(f"Installed service file at: {service_file}")
        print(f"Local copy created at: {local_service_path}")

        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
        return True
    except Exception as e:
        print(f"Error installing service file: {e}")
        return False


def _install_script():
    """Install this script to a PATH directory or add shell rc export."""
    script_path = os.path.realpath(__file__)
    script_name = os.path.basename(script_path).rsplit('.', 1)[0]

    st = os.stat(script_path)
    os.chmod(script_path, st.st_mode | 0o111)

    for p in os.environ.get('PATH', '').split(':'):
        if not p or not os.path.isdir(p):
            continue
        link_path = os.path.join(p, script_name)
        if os.path.islink(link_path) and os.path.realpath(link_path) == script_path:
            print(f"Already installed at: {link_path}")
            return
        try:
            if os.path.islink(link_path) or os.path.exists(link_path):
                os.remove(link_path)
            os.symlink(script_path, link_path)
            print(f"Installed to: {link_path}")
            return
        except (PermissionError, OSError):
            continue

    shell = os.environ.get('SHELL', '/bin/bash')
    rc_file = os.path.expanduser('~/.zshrc') if 'zsh' in shell else os.path.expanduser('~/.bashrc')
    export_line = f'export {script_name}="{script_path}"'

    if os.path.exists(rc_file):
        with open(rc_file) as f:
            if export_line in f.read():
                print(f"Already exported in {rc_file}")
                print(f"  {export_line}")
                return

    with open(rc_file, 'a') as f:
        f.write(f'\n# Telegram Tools\nexport {script_name}="{script_path}"\n')

    print(f"Added to {rc_file}: {export_line}")
    print(f"Run: source {rc_file}")


def _uninstall_script():
    """Remove symlinks and rc exports for this script."""
    script_path = os.path.realpath(__file__)
    script_name = os.path.basename(script_path).rsplit('.', 1)[0]

    found = shutil.which(script_name)
    removed = False
    if found and os.path.islink(found):
        real = os.path.realpath(found)
        if real == script_path:
            try:
                os.remove(found)
                print(f"Removed symlink: {found}")
                removed = True
            except OSError as e:
                print(f"Error removing symlink: {e}")

    if not removed:
        print(f"No symlink found for '{script_name}' in PATH")

    for rc in ('~/.bashrc', '~/.zshrc'):
        rc_path = os.path.expanduser(rc)
        if not os.path.exists(rc_path):
            continue
        export_line = f'export {script_name}="{script_path}"'
        with open(rc_path) as f:
            lines = f.readlines()
        filtered = [l for l in lines if export_line not in l]
        if len(filtered) != len(lines):
            with open(rc_path, 'w') as f:
                f.writelines(filtered)
            print(f"Removed export from {rc_path}")


def manage_service(command):
    """Handles systemd service management."""
    if command == 'install':
        _install_script()

    if command == 'start':
        generate_service_file()

    if command == 'uninstall':
        _uninstall_script()

    actions = {
        'start': ['systemctl', '--user', 'enable', '--now', 'tgd.service'],
        'stop': ['systemctl', '--user', 'stop', 'tgd.service'],
        'restart': ['systemctl', '--user', 'restart', 'tgd.service'],
        'status': ['systemctl', '--user', 'status', 'tgd.service'],
        'logs': ['journalctl', '--user', '-u', 'tgd.service', '-f'],
        'uninstall': ['systemctl', '--user', 'disable', '--now', 'tgd.service'],
    }

    if command not in actions:
        print(f"Unknown command: {command}")
        return

    try:
        if command == 'logs':
            subprocess.run(actions[command])
        else:
            result = subprocess.run(actions[command], capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print(result.stderr)

            if command == 'uninstall':
                service_file = os.path.expanduser("~/.config/systemd/user/tgd.service")
                local_service = os.path.join(os.path.dirname(os.path.realpath(__file__)), "tgd.service")
                
                for f in [service_file, local_service]:
                    if os.path.exists(f):
                        os.remove(f)
                        print(f"Removed: {f}")
                
                subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
                print("Cleanup complete.")
    except Exception as e:
        print(f"Error executing {command}: {e}")


def print_usage():
    print("Usage: python3 tgd.py [option]")
    print("\nOptions:")
    print("  run        Run the daemon in current terminal")
    print("  install    Install this script to system path")
    print("  start      Enable and start the systemd service")
    print("  stop       Stop the systemd service")
    print("  restart    Restart the systemd service")
    print("  status     Show the status of the systemd service")
    print("  logs       Follow the service logs")
    print("  uninstall  Remove this script from system path and disable systemd service")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == 'run':
        run_daemon()
    elif cmd in ['install', 'start', 'stop', 'restart', 'status', 'logs', 'uninstall']:
        manage_service(cmd)
    else:
        print_usage()
        sys.exit(1)
