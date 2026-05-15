## Tmux Command (`/tmux`)

A built-in command that uses `handle_callback` for interactive tmux session management:

- **`/tmux`** — Shows an inline keyboard with **Start** / **Stop** / **List** buttons
- **Start** creates a new tmux session, **Stop** kills all sessions, **List** shows active sessions
- The `run()` function sends the initial message with buttons; `handle_callback()` processes each button press via `editMessageText` and `answerCallbackQuery`
