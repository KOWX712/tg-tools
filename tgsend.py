#!/usr/bin/env python3

import os
import sys
import requests
import shutil
import subprocess
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_notification(message, urgency="normal", icon="telegram"):
    """Sends a desktop notification using notify-send."""
    if shutil.which("notify-send"):
        try:
            subprocess.run(["notify-send", "-u", urgency, "-i", icon, "Telegram Tool", message], check=False)
        except Exception as e:
            print(f"Failed to send notification: {e}")


def send_file(file_path):
    """
    Sends a file to a Telegram chat using the Telegram Bot API.
    """
    if not BOT_TOKEN or not CHAT_ID:
        env_path = os.path.join(SCRIPT_DIR, ".env")
        print("Error: BOT_TOKEN or CHAT_ID not found.")
        print(f"Looked in: {env_path}")
        return False

    if not os.path.isfile(file_path):
        print(f"Error: File '{file_path}' not found.")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

    print(f"Sending {os.path.basename(file_path)}...")
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': CHAT_ID}
            response = requests.post(url, data=data, files=files, timeout=30)

        if response.status_code == 200:
            success_msg = f"Successfully sent: {os.path.basename(file_path)}"
            print(success_msg)
            send_notification(success_msg)
            return True
        else:
            fail_msg = f"Failed to send file. Status code: {response.status_code}"
            print(fail_msg)
            print(f"Response: {response.text}")
            send_notification(fail_msg, urgency="critical")
            return False

    except requests.exceptions.Timeout:
        timeout_msg = f"Error: Connection timed out while sending {os.path.basename(file_path)}."
        print(timeout_msg)
        send_notification(timeout_msg, urgency="critical")
        return False
    except Exception as e:
        error_msg = f"An error occurred: {e}"
        print(error_msg)
        send_notification(error_msg, urgency="critical")
        return False


def install_kde_service():
    """Installs KDE service menu."""
    python_path = sys.executable
    script_path = os.path.realpath(__file__)

    desktop_content = f"""[Desktop Entry]
Type=Service
MimeType=all/allfiles;
Actions=sendToTelegram
ServiceTypes=KonqPopupMenu/Plugin
X-KDE-Priority=TopLevel

[Desktop Action sendToTelegram]
Name=Send via Telegram Bot
Icon=telegram
Exec={python_path} {script_path} %F
"""
    # Path for KDE service menu
    system_menu_file = os.path.expanduser("~/.local/share/kio/servicemenus/tgsend.desktop")

    try:
        os.makedirs(os.path.dirname(system_menu_file), exist_ok=True)
        with open(system_menu_file, "w") as f:
            f.write(desktop_content)
        os.chmod(system_menu_file, 0o755)

        print(f"KDE service menu installed at: {system_menu_file}")
        return True
    except Exception as e:
        print(f"Error installing KDE service menu: {e}")
        return False


def uninstall_kde_service():
    """Removes the KDE service menu."""
    system_menu_file = os.path.expanduser("~/.local/share/kio/servicemenus/tgsend.desktop")

    if os.path.exists(system_menu_file):
        os.remove(system_menu_file)
        print(f"Removed: {system_menu_file}")
    else:
        print(f"Not found: {system_menu_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: tgsend.py <file1> <file2> ...")
        print("       tgsend.py install-service kde")
        print("       tgsend.py uninstall")
    else:
        cmd = sys.argv[1].lower()
        if cmd == 'install-service' and len(sys.argv) > 2 and sys.argv[2].lower() == 'kde':
            install_kde_service()
        elif cmd == 'uninstall':
            uninstall_kde_service()
        else:
            files_to_send = sys.argv[1:]
            for file_path in files_to_send:
                send_file(file_path)
