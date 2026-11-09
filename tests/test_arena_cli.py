from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from cli.arena import main as arena_main
from shared.case_instances import expand_name_tokens, resolve_profile_selector
from shared.case_spec import parse_case_spec


def test_arena_help() -> None:
    runner = CliRunner()
    result = runner.invoke(arena_main, ['-h'])
    assert result.exit_code == 0
    assert 'init' in result.output
    assert 'check' in result.output
    assert 'summary' in result.output
    assert 'list' in result.output


def test_arena_list_global() -> None:
    import os

    repo = Path(__file__).resolve().parents[1]
    runner = CliRunner()
    old = os.getcwd()
    try:
        os.chdir(repo)
        result = runner.invoke(arena_main, ['list'])
    finally:
        os.chdir(old)
    assert result.exit_code == 0, result.output
    assert 'case001-4llm-demo' in result.output


def test_arena_init_help_mentions_case_and_rebuild() -> None:
    runner = CliRunner()
    result = runner.invoke(arena_main, ['init', '-h'])
    assert result.exit_code == 0
    assert '--case' in result.output
    assert '--rebuild' in result.output
    assert '--no-key' in result.output


def test_arena_init_unknown_name() -> None:
    import os

    repo = Path(__file__).resolve().parents[1]
    runner = CliRunner()
    old = os.getcwd()
    try:
        os.chdir(repo)
        result = runner.invoke(
            arena_main,
            ['init', '--case', 'not-a-real-case', '--no-key'],
        )
    finally:
        os.chdir(old)
    assert result.exit_code == 1
    assert 'not supported yet' in result.output
    assert 'templates/case/not-a-real-case.yaml' in result.output


def test_arena_check() -> None:
    repo = Path(__file__).resolve().parents[1]
    case_yaml = repo / 'case' / 'case001-4llm-demo' / 'case.yaml'
    if not case_yaml.is_file():
        return
    import os

    runner = CliRunner()
    old = os.getcwd()
    try:
        os.chdir(repo)
        result = runner.invoke(arena_main, ['check', '--case', 'case001-4llm-demo'])
    finally:
        os.chdir(old)
    assert result.exit_code == 0, result.output
    assert 'ssj-ds' in result.output
    assert 'ssj-mimo' in result.output


def test_expand_name_comma_separated() -> None:
    assert expand_name_tokens(('ds, kimi', 'jev')) == ('ds', 'kimi', 'jev')


def test_resolve_name_accepts_instance_dir() -> None:
    repo = Path(__file__).resolve().parents[1]
    spec = parse_case_spec(repo / 'case' / 'case001-4llm-demo' / 'case.yaml')
    assert resolve_profile_selector(spec, 'ds') == 'ds'
    assert resolve_profile_selector(spec, 'ssj-jev') == 'jev'
