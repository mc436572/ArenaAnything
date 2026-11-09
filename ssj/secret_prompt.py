"""密钥输入：终端只显示两端各 5 个字符，中间为 *。"""

from __future__ import annotations

import sys

from cli.console import CONSOLE
from ssj.settings import mask_edges

_PASTE_ON = '\x1b[200~'
_PASTE_OFF = '\x1b[201~'


def prompt_masked_secret(label: str) -> str:
    """读取一行密钥。交互终端里随着输入刷新打码结果；管道输入则读完再打印打码。"""
    if not sys.stdin.isatty():
        value = sys.stdin.readline().rstrip('\r\n')
        CONSOLE.print(mask_edges(value))
        return value
    return _read_tty(label)


def _redraw(label: str, value: str) -> None:
    shown = mask_edges(value)
    # 先清行再 \r：WSL/部分终端对单独 \r 回列首不可靠，粘贴时逐字 redraw 会叠行。
    sys.stdout.write(f'\033[2K\r{label}{shown}')
    sys.stdout.flush()


def _is_paste_prefix(text: str) -> bool:
    return _PASTE_ON.startswith(text) or _PASTE_OFF.startswith(text)


def _read_tty(label: str) -> str:
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    chars: list[str] = []
    pending = ''
    in_paste = False
    sys.stdout.write('\x1b[?2004h')
    sys.stdout.flush()
    try:
        tty.setcbreak(fd)
        _redraw(label, '')
        while True:
            ch = sys.stdin.read(1)
            if pending or ch == '\x1b':
                pending += ch
                if pending == _PASTE_ON:
                    pending = ''
                    in_paste = True
                    continue
                if pending == _PASTE_OFF:
                    pending = ''
                    in_paste = False
                    _redraw(label, ''.join(chars))
                    continue
                if _is_paste_prefix(pending):
                    continue
                pending = ''
                continue
            if ch in ('\r', '\n'):
                sys.stdout.write('\n')
                sys.stdout.flush()
                break
            if ch in ('\x7f', '\b'):
                if chars:
                    chars.pop()
                _redraw(label, ''.join(chars))
                continue
            if ch == '\x15':
                chars.clear()
                _redraw(label, '')
                continue
            if ch == '\x03':
                sys.stdout.write('\n')
                sys.stdout.flush()
                raise KeyboardInterrupt
            if ord(ch) < 32:
                continue
            chars.append(ch)
            if not in_paste:
                _redraw(label, ''.join(chars))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write('\x1b[?2004l')
        sys.stdout.flush()
    return ''.join(chars)
