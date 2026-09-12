# Release checklist

Current local status (2026-09-12): offline smoke, tests, claim audit,
optimizer parity, official archive validation, and full-data reproduction pass.
The raw archive and Parquet partitions remain local and gitignored.

- [x] Run the equivalent offline smoke/test gates and full reproduction commands (`python -m src.pipeline`, `python -m pytest`, and full mode); GNU Make is not installed on this Windows host.
- [x] Inspect `reports/run_manifest.json`, policy-value intervals, and all guardrails.
- [x] Confirm README and artifacts distinguish measured, estimated, and simulated quantities.
- [x] Confirm no raw Criteo rows, caches, or trained models are tracked.
- [x] Commit the verified changes with an imperative message.
- [ ] Create the local `v1.0` tag only after the full-data acceptance checks pass.
