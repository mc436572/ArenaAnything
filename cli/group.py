"""Click group helpers."""

from __future__ import annotations

import click


class SsjGroup(click.Group):
    """List nested subgroup commands on the root help (e.g. config setup)."""

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        rows: list[tuple[str, str]] = []

        def walk(prefix: str, group: click.Group) -> None:
            for sub in sorted(group.list_commands(ctx)):
                sub_cmd = group.get_command(ctx, sub)
                if sub_cmd is None:
                    continue
                label = f'{prefix} {sub}'.strip()
                if isinstance(sub_cmd, click.Group):
                    walk(label, sub_cmd)
                else:
                    rows.append((label, sub_cmd.get_short_help_str() or ''))

        for name in sorted(self.list_commands(ctx)):
            cmd = self.get_command(ctx, name)
            if cmd is None:
                continue
            if isinstance(cmd, click.Group):
                walk(name, cmd)
            else:
                rows.append((name, cmd.get_short_help_str() or ''))
        if rows:
            with formatter.section('Commands'):
                formatter.write_dl(rows)
