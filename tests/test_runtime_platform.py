from __future__ import annotations

import pytest

from shared.runtime_platform import require_linux_or_wsl


def test_rejects_windows_native_python(monkeypatch) -> None:
    monkeypatch.setattr('shared.runtime_platform.sys.platform', 'win32')
    with pytest.raises(SystemExit, match='WSL'):
        require_linux_or_wsl()


def test_allows_linux(monkeypatch) -> None:
    monkeypatch.setattr('shared.runtime_platform.sys.platform', 'linux')
    require_linux_or_wsl()
