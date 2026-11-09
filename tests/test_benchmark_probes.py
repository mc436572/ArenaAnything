from __future__ import annotations

from pathlib import Path

import pytest

from shared.benchmark_probes import (
    BenchmarkProbeError,
    load_probe_items,
    list_suite_names,
    repo_benchmark_root,
    resolve_probe_file,
)


def test_manifest_lists_known_suites() -> None:
    names = list_suite_names(repo_benchmark_root(Path(__file__).resolve().parents[1]))
    assert names == ["ceval", "cmmlu", "demo", "mmlu"]


def test_demo_has_thirty_items_with_answers() -> None:
    root = repo_benchmark_root(Path(__file__).resolve().parents[1])
    items = load_probe_items("demo", root)
    assert len(items) == 30
    assert all(item.get("answer") in {"A", "B", "C", "D"} for item in items)


def test_unknown_suite_raises() -> None:
    root = repo_benchmark_root(Path(__file__).resolve().parents[1])
    with pytest.raises(BenchmarkProbeError):
        resolve_probe_file("nope", root)
