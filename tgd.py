#!/usr/bin/env python3

import os
import sys
import time
import requests
import subprocess
import signal
from dotenv import load_dotenv

# Load environment variables
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DOWNLOAD_DIR = os.path.expanduser("~/Downloads")

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
        return

    try:
        if tool == 'wl-copy':
            subprocess.run(['wl-copy'], input=text.encode(), check=True)
        elif tool == 'xclip':
            subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode(), check=True)
        elif tool == 'xsel':
            subprocess.run(['xsel', '--clipboard', '--input'], input=text.encode(), check=True)

        print(f"Copied to clipboard using {tool}: {text[:50]}...")
    except Exception as e:
        print(f"Failed to copy to clipboard: {e}")


def download_file(file_id, file_name):
    """Downloads a file from Telegram."""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
        params = {'file_id': file_id}
        response = requests.get(url, params=params, timeout=10).json()

        if not response.get('ok'):
            print(f"Failed to get file info: {response}")
            return

        file_path = response['result']['file_path']
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        if not file_name:
            file_name = os.path.basename(file_path)

        local_path = os.path.join(DOWNLOAD_DIR, file_name)

        print(f"Downloading {file_name}...")
        file_data = requests.get(download_url, timeout=30).content
        with open(local_path, 'wb') as f:
            f.write(file_data)
        print(f"Saved to {local_path}")

    except Exception as e:
        print(f"Error downloading file: {e}")


def process_message(message):
    """Processes an individual message."""
    msg_chat_id = str(message['chat']['id'])
    if msg_chat_id != str(CHAT_ID):
        print(f"Ignored message from unauthorized chat: {msg_chat_id}")
        return

    if 'text' in message:
        copy_to_clipboard(message['text'])
    elif 'document' in message:
        doc = message['document']
        download_file(doc['file_id'], doc.get('file_name'))
    elif 'photo' in message:
        photo = message['photo'][-1]
        download_file(photo['file_id'], None)
    elif 'video' in message:
        video = message['video']
        download_file(video['file_id'], video.get('file_name'))


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


def manage_service(command):
    """Handles systemd service management."""
    if command == 'start':
        generate_service_file()

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
    print("  start      Enable and start the systemd service")
    print("  stop       Stop the systemd service")
    print("  restart    Restart the systemd service")
    print("  status     Show the status of the systemd service")
    print("  logs       Follow the service logs")
    print("  uninstall  Disable and stop the systemd service")

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
