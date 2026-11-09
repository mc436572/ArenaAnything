"""Post-init connectivity: ssj model ping in each ssj-<profile>/ via frozen bundle."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

_ANSI = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
_BOX_CHARS = frozenset('╭╮╰╯│─┌┐└┘')


@dataclass(frozen=True)
class ProfilePingResult:
    profile: str
    instance_dir: str
    ok: bool
    detail: str


def _strip_ansi(text: str) -> str:
    return _ANSI.sub('', text)


_PING_OK_LINE = re.compile(r'#\d+:\s*ok\s*\(([0-9.]+)s\)', re.IGNORECASE)


def summarize_ping_log(log: str) -> str:
    """Failure detail: one line, no Rich box borders."""
    text = _strip_ansi(log).strip()
    if not text:
        return 'no output'
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if any(ch in ln for ch in _BOX_CHARS):
            continue
        if _PING_OK_LINE.search(ln):
            continue
        low = ln.lower().strip('- ').strip()
        if low == 'pong' or low.startswith('noul='):
            continue
        if len(ln) > 160:
            continue
        return ln
    return 'no output'


def success_ping_detail(log: str) -> str:
    """Optional latency only; omit model-specific reply (pong / noul=…)."""
    text = _strip_ansi(log)
    for ln in text.splitlines():
        m = _PING_OK_LINE.search(ln)
        if m:
            return f'{m.group(1)}s'
    return ''


def _ping_one_profile(
    *,
    case_dir: Path,
    agent_line: str,
    agent_version: str,
    profile: str,
) -> ProfilePingResult:
    from shared.case_workspace import instance_dir_name
    from shared.ssj_subprocess import run_ssj_in_instance

    name = str(profile).strip()
    inst_name = instance_dir_name(agent_line, name)
    inst = case_dir / inst_name
    try:
        proc = run_ssj_in_instance(
            inst,
            ['model', 'ping'],
            agent_version=agent_version,
            capture_output=True,
            timeout=120.0,
        )
    except FileNotFoundError as exc:
        return ProfilePingResult(name, inst_name, False, str(exc))
    log = ((proc.stdout or '') + (proc.stderr or '')).strip()
    ok = proc.returncode == 0
    if ok:
        detail = success_ping_detail(log)
    elif log:
        detail = summarize_ping_log(log)[:500]
    else:
        detail = f'exit {proc.returncode}'
    return ProfilePingResult(name, inst_name, ok, detail)


def ping_case_profiles(
    *,
    case_dir: Path,
    agent_line: str,
    agent_version: str,
    profiles: list[str],
    max_workers: int | None = None,
) -> list[ProfilePingResult]:
    names = [str(p).strip() for p in profiles if str(p).strip()]
    if not names:
        return []
    workers = max_workers if max_workers is not None else min(8, len(names))
    workers = max(1, workers)
    by_profile: dict[str, ProfilePingResult] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _ping_one_profile,
                case_dir=case_dir,
                agent_line=agent_line,
                agent_version=agent_version,
                profile=name,
            ): name
            for name in names
        }
        for fut in as_completed(futures):
            row = fut.result()
            by_profile[row.profile] = row
    return [by_profile[n] for n in names if n in by_profile]
