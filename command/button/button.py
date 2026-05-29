#!/usr/bin/env python3

import html as htmlmod
import re
import requests

COMMAND = "button"
HELP = "Create message with inline buttons"

API_BASE = "https://api.telegram.org/bot"

# Pattern: [Text](buttonurl[#style]://URL[:same])
# Groups: (1)label (2)style (3)url (4):same
BUTTON_PATTERN = re.compile(
    r'\[([^\]]+)\]\(buttonurl(?:#(\w+))?://(.+?)(:same)?\)'
)

# Detect markdown-like formatting in raw text
MD_BOLD = re.compile(r'\*\*(.+?)\*\*')
MD_ITALIC = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')
MD_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)')
MD_CODE = re.compile(r'`([^`]+)`')


def _api(method, token, data):
    url = f"{API_BASE}{token}/{method}"
    try:
        r = requests.post(url, json=data, timeout=10)
        result = r.json()
        if not result.get('ok'):
            print(f"[button] API {method} failed: {result}", flush=True)
        return result
    except Exception as e:
        print(f"[button] API {method} error: {e}", flush=True)
        return None


def _build_entity_tree(entities):
    """Build tree from entities to handle nesting (blockquote>bold, bold>link, etc.)."""
    # Parent-first sort: offset ASC, length DESC
    sorted_ents = sorted(entities, key=lambda e: (e['offset'], -e['length']))

    root = {'children': [], 'offset': 0, 'length': 0, 'type': '_root'}
    stack = [root]

    for ent in sorted_ents:
        node = {**ent, 'children': []}
        ent_start = ent['offset']
        ent_end = ent['offset'] + ent['length']

        # Walk stack up until current entity fits inside a parent
        while len(stack) > 1:
            parent = stack[-1]
            parent_start = parent['offset']
            parent_end = parent['offset'] + parent['length']
            if ent_start >= parent_start and ent_end <= parent_end:
                break
            stack.pop()

        stack[-1]['children'].append(node)
        stack.append(node)

    return root


def _render_entity_tree(text, node):
    """Recursively render entity tree to HTML."""
    if node['type'] == '_root':
        result = []
        pos = 0
        for child in node['children']:
            if child['offset'] > pos:
                result.append(htmlmod.escape(text[pos:child['offset']]))
            result.append(_render_entity_tree(text, child))
            pos = child['offset'] + child['length']
        if pos < len(text):
            result.append(htmlmod.escape(text[pos:]))
        return ''.join(result)

    ent_start = node['offset']
    ent_end = node['offset'] + node['length']

    inner = []
    pos = ent_start
    for child in node.get('children', []):
        if child['offset'] > pos:
            inner.append(htmlmod.escape(text[pos:child['offset']]))
        inner.append(_render_entity_tree(text, child))
        pos = child['offset'] + child['length']
    if pos < ent_end:
        inner.append(htmlmod.escape(text[pos:ent_end]))

    inner_html = ''.join(inner)
    etype = node['type']

    if etype == 'bold':
        return f'<b>{inner_html}</b>'
    elif etype == 'italic':
        return f'<i>{inner_html}</i>'
    elif etype == 'underline':
        return f'<u>{inner_html}</u>'
    elif etype == 'strikethrough':
        return f'<s>{inner_html}</s>'
    elif etype == 'spoiler':
        return f'<tg-spoiler>{inner_html}</tg-spoiler>'
    elif etype == 'code':
        return f'<code>{inner_html}</code>'
    elif etype == 'pre':
        lang = node.get('language', '')
        if lang:
            return f'<pre><code class="language-{lang}">{inner_html}</code></pre>'
        return f'<pre>{inner_html}</pre>'
    elif etype == 'text_link':
        url = node.get('url', '')
        return f'<a href="{url}">{inner_html}</a>'
    elif etype == 'text_mention':
        uid = node.get('user', {}).get('id', '')
        return f'<a href="tg://user?id={uid}">{inner_html}</a>'
    elif etype in ('blockquote', 'expandable_blockquote'):
        return f'<blockquote>{inner_html}</blockquote>'
    else:
        return inner_html


def _entities_to_html(text, entities):
    """Convert plain text + Telegram entities to HTML with proper nesting."""
    if not entities:
        return htmlmod.escape(text)

    tree = _build_entity_tree(entities)
    return _render_entity_tree(text, tree)


def _raw_markdown_to_html(text):
    """Convert common markdown syntax in raw text to HTML.

    Handles: **bold**, *italic*, `code`, [text](url)
    Non-destructive: if no patterns found, returns escaped text.
    """
    if not text:
        return text

    has_md = bool(MD_BOLD.search(text) or MD_ITALIC.search(text)
                  or MD_LINK.search(text) or MD_CODE.search(text))
    if not has_md:
        return htmlmod.escape(text)

    text = MD_LINK.sub(r'<a href="\2">\1</a>', text)
    text = MD_BOLD.sub(r'<b>\1</b>', text)
    text = MD_ITALIC.sub(r'<i>\1</i>', text)
    text = MD_CODE.sub(r'<code>\1</code>', text)
    return text


def _strip_button_patterns(text):
    """Remove [Text](buttonurl://URL) formatting instructions from text."""
    return BUTTON_PATTERN.sub('', text).strip()


def _strip_and_adjust_entities(text, entities, pattern):
    """Strip pattern matches from text and adjust entity offsets.

    Entities that overlap with removed pattern regions are dropped.
    Returns (cleaned_text, adjusted_entities).
    """
    removals = [(m.start(), m.end()) for m in pattern.finditer(text)]

    adjusted = []
    for ent in entities:
        start = ent['offset']
        end = start + ent['length']

        removed_before = sum(
            rm_end - rm_start
            for rm_start, rm_end in removals
            if rm_end <= start
        )

        overlaps = any(
            start < rm_end and end > rm_start
            for rm_start, rm_end in removals
        )

        if not overlaps:
            adjusted.append({
                'offset': start - removed_before,
                'length': ent['length'],
                'type': ent['type'],
                **({k: ent[k] for k in ('url', 'language', 'user') if k in ent}),
            })

    cleaned = pattern.sub('', text).strip()
    return cleaned, adjusted


def _parse_buttons(text):
    """Parse [Text](buttonurl://URL[:same]) definitions into inline_keyboard rows."""
    lines = text.rstrip('\n').split('\n')
    buttons = []

    for line in lines:
        stripped = line.strip()
        match = BUTTON_PATTERN.match(stripped)
        if match:
            buttons.append({
                'text': match.group(1),
                'url': match.group(3),
                'style': match.group(2),
                'same_line': match.group(4) == ':same',
            })

    keyboard = []
    current_row = []

    for btn in buttons:
        button_data = {'text': btn['text'], 'url': btn['url']}
        if btn['style']:
            button_data['style'] = btn['style']

        if btn['same_line']:
            current_row.append(button_data)
        else:
            if current_row:
                keyboard.append(current_row)
            current_row = [button_data]

    if current_row:
        keyboard.append(current_row)

    return keyboard


def _get_message_text(text):
    """Extract non-button lines from text."""
    lines = text.rstrip('\n').split('\n')
    msg_lines = [l for l in lines if not BUTTON_PATTERN.match(l.strip())]
    return '\n'.join(msg_lines).strip()


def _send_message(chat_id, msg_text, bot_token, parse_mode=None, keyboard=None):
    payload = {
        'chat_id': chat_id,
        'text': msg_text,
        'link_preview_options': {'is_disabled': True},
    }
    if keyboard:
        payload['reply_markup'] = {'inline_keyboard': keyboard}
    if parse_mode:
        payload['parse_mode'] = parse_mode

    btn_count = len(keyboard) if keyboard else 0
    print(f"[button] sending: chat={chat_id} parse_mode={parse_mode} "
          f"text_len={len(msg_text)} buttons={btn_count}", flush=True)

    result = _api('sendMessage', bot_token, payload)
    if result and result.get('ok'):
        print(f"[button] message sent: {result.get('result', {}).get('message_id')}", flush=True)
        return True
    else:
        print(f"[button] send failed", flush=True)
        return False


def run(message, bot_token):
    """Handles /button — format message with inline buttons."""
    chat_id = message['chat']['id']
    text = message.get('text', '')

    print(f"[button] run() — msg_id={message.get('message_id')} "
          f"has_reply={'reply_to_message' in message} "
          f"text={repr(text[:80])}", flush=True)

    is_reply = 'reply_to_message' in message

    if is_reply:
        reply = message['reply_to_message']
        source = reply.get('text') or reply.get('caption') or ''
        entities = reply.get('entities') or reply.get('caption_entities') or []

        if not source:
            return 'No text content in replied message.'

        keyboard = _parse_buttons(source)

        if entities:
            clean_text, adj_entities = _strip_and_adjust_entities(
                source, entities, BUTTON_PATTERN
            )
            msg_text = _entities_to_html(clean_text, adj_entities)
        elif '*' in source or '[' in source:
            msg_text = _raw_markdown_to_html(source)
            msg_text = BUTTON_PATTERN.sub('', msg_text).strip()
        else:
            msg_text = _strip_button_patterns(source)
            msg_text = htmlmod.escape(msg_text) if msg_text else '.'

        parse_mode = 'HTML' if (entities or '<' in msg_text) else None

        _send_message(chat_id, msg_text, bot_token,
                      parse_mode=parse_mode,
                      keyboard=keyboard if keyboard else None)
    else:
        parts = text.split(maxsplit=1)
        content = parts[1] if len(parts) > 1 else ''

        keyboard = _parse_buttons(content)

        if not keyboard:
            return (
                "Usage: Send a message with /button followed by "
                "text and button definitions.\n\n"
                "Example:\n"
                "/button Hello\n"
                "[GitHub](buttonurl://https://github.com)"
            )

        msg_text = _get_message_text(content) or '.'
        _send_message(chat_id, msg_text, bot_token, parse_mode=None,
                      keyboard=keyboard)

    return ''


def handle_callback(callback_query, bot_token):
    """Handles button clicks (URL buttons don't need callback handling)."""
    pass
