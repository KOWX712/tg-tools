#!/usr/bin/env python3

COMMAND = "hello"
HELP = "Send a greeting"


def run(message: dict, bot_token: str) -> str:
    """Handles the /hello command.

    Args:
        message: The Telegram message dict.
        bot_token: The bot token for API calls.

    Returns:
        The response text to send back.
    """
    return "hi"
