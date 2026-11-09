# ssj whiteboard @ 0.1.0 (frozen)

**Line:** `ssj` · **Version:** `0.1.0` · **Mode:** single-turn chat + static MCQ eval (no Gate / Skill / MCP)

## Scope (process root / ssj CLI)

| Capability | Notes |
|------------|--------|
| `ssj setup` / `model` / `config` | Per process root; secrets in `.env` only |
| `ssj chat` | OpenAI-compatible chat; JEV default profile cannot chat (use eval/ping) |
| `ssj eval` | `--suite` + `--with-profile`; JEV via SystemOne decisions; chat models via messages |
| Transport | `shared/model_transport.py` — chat vs decisions by LiteLLM prefix |
| Reply / MCQ | `shared/model_reply.py` — per-model extract + parse (e.g. MiMo `reasoning` fallback) |
| Eval progress file | Optional env **`SSJ_PROGRESS_FILE`** + **`SSJ_PROGRESS_STEP`** (default 5): terminal Rich bar + throttled JSON snapshots for **arena** |

## Arena (repo engine, same `pip install -e .`)

Case 工作区与 `case.yaml` 不在本模板目录内；编排命令：

| Command | Purpose |
|---------|---------|
| `arena init <case_id>` | Materialize `case/<case_id>/` + copy this template → each `ssj-<profile>/` |
| `arena check --name …` | Validate + list instances and key readiness |
| `arena run --name … all` | Subprocess `ssj eval` per cell; **`arena summary`** on success |
| `arena summary --name …` | `export/summary.json` + `export/index.html` |

`arena run` sets per-cell `SSJ_PROGRESS_FILE` under `reports/.progress/` and shows aggregate Rich progress.

Each subprocess: **`cwd` = `SSJ_ROOT` = absolute `ssj-<profile>/`**; **`PYTHONPATH`** = `case/<id>/ssj/<ver>/` from frozen **`ssj-<ver>.tar.gz`** (no pip in Case); parent API keys and `SSJ_MODEL` are not inherited (`shared/ssj_subprocess.py`).

The bundle `templates/ssj/0.1.0/ssj-0.1.0.tar.gz` is built by maintainers and committed here. **`arena init`** extracts it to `case/<id>/ssj/0.1.0/`.

## Pinned in this directory

- `models.yaml` — alias → `litellm` ids (materialize copies as-is, then sets `default` to Case profile)
- `chat-profiles/demo-profile.yaml` — eval preset (`demo-profile`, `max_tokens: 256` for reasoning models)
- `config.yaml` — trace/session layout (no secrets)

## Secrets (not in this tree)

Each `ssj-<profile>/` process root needs its own `.env` (see `.env.example`). Never commit `.env` or export secrets.

## Known issues @ 0.1.0

- Kimi (`moonshot/…`): region / key / platform must match `MOONSHOT_API_BASE`; may be skipped in a Case matrix.
- JEV via OpenRouter: geo restrictions; direct `typesafe/jev-latest` + `TYPESAFE_*` recommended.
- MiMo: use sufficient `max_tokens` in eval profile (reasoning models).

## Version policy (0.1.x)

- **Patch** (`0.1.1`, …): new directory under `templates/ssj/<version>/`; template tweaks; Cases pin `agent.version` in `case.yaml`.
- **Minor** (`0.2.0`): breaking Case contract — not a 0.1.x bump.

**Engine** (`cli/` + `shared/`): evolves on the branch you install; re-run `pip install -e .` after pull. Example Case: `case/case001-4llm-demo/` (ds / kimi / jev / mimo × demo).
