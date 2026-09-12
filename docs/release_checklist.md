# Release checklist

Current local status (2026-09-12): offline smoke, tests, claim audit, and
optimizer parity pass. The full-data gate is pending because the official
Criteo endpoint is not reachable from this environment; `make download-criteo`
writes `data/raw/criteo/download_error.json` and retains no partial archive.

- [ ] Run `make build`, `make test`, and (after downloading Criteo) `make reproduce-full`.
- [ ] Inspect `reports/run_manifest.json`, policy-value intervals, and all guardrails.
- [ ] Confirm README and artifacts distinguish measured, estimated, and simulated quantities.
- [ ] Confirm no raw Criteo rows, caches, or trained models are tracked.
- [ ] Commit the verified changes with an imperative message.
- [ ] Create the local `v1.0` tag only after the full-data acceptance checks pass.
