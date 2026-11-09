"""Load LLM probe suites from benchmark/manifest.yaml (git-published jsonl)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

MANIFEST_REL = Path("benchmark") / "manifest.yaml"
KNOWN_SUITES = frozenset({"ceval", "cmmlu", "mmlu", "demo"})


class BenchmarkProbeError(ValueError):
    pass


def repo_benchmark_root(start: Path | None = None) -> Path:
    """Locate benchmark/ (manifest + jsonl) by walking up from start or cwd."""
    cur = (start or Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        manifest = parent / MANIFEST_REL
        if manifest.is_file():
            return parent / "benchmark"
    raise BenchmarkProbeError(
        f"Cannot find {MANIFEST_REL}. Run from ArenaAnything repo or set cwd to repo root."
    )


def load_manifest(benchmark_dir: Path | None = None) -> dict:
    root = benchmark_dir or repo_benchmark_root()
    path = root / "manifest.yaml"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "suites" not in data:
        raise BenchmarkProbeError(f"Invalid manifest: {path}")
    return data


def list_suite_names(benchmark_dir: Path | None = None) -> list[str]:
    manifest = load_manifest(benchmark_dir)
    suites = manifest.get("suites") or {}
    return sorted(str(k) for k in suites.keys())


def resolve_probe_file(suite: str, benchmark_dir: Path | None = None) -> Path:
    name = suite.strip().lower()
    manifest = load_manifest(benchmark_dir)
    suites = manifest.get("suites") or {}
    if name not in suites:
        known = ", ".join(sorted(suites.keys()))
        raise BenchmarkProbeError(f"Unknown probe suite {suite!r}. Known: {known}")
    rel = suites[name].get("file")
    if not rel:
        raise BenchmarkProbeError(f"Suite {name!r} has no file in manifest.")
    root = benchmark_dir or repo_benchmark_root()
    path = (root / str(rel)).resolve()
    if not path.is_file():
        raise BenchmarkProbeError(f"Probe file missing for suite {name!r}: {path}")
    return path


def load_probe_items(suite: str, benchmark_dir: Path | None = None) -> list[dict]:
    path = resolve_probe_file(suite, benchmark_dir)
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
