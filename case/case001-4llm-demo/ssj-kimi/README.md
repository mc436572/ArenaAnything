# ssj @0.1.0 process-root template

Frozen whiteboard **individual** copied into `case/<case-id>/ssj-<profile>/` by **`arena init <case_id>`**.

- **`models.yaml`** is copied from this directory; materialize then sets `default` to the Case profile (`ds`, `kimi`, …).
- Fill **`.env`** in each instance (see `.env.example`); keys are not copied from the repo root.
- **Arena flow:** `arena init <case_id>` → keys → `arena check --name …` → `arena run --name … all` (auto summary).
- **Eval progress (orchestrated runs):** when `SSJ_PROGRESS_FILE` is set (arena does this), `ssj eval` keeps the terminal progress bar and writes throttled JSON (`SSJ_PROGRESS_STEP`, default 5).

Details: [RELEASE.md](./RELEASE.md)
