# Repository Guidelines

## Project Structure & Module Organization

This repository describes an incentive-allocation and budget-constrained decision engine. The implementation should follow the structure in `increment_decision_engine_project_plan.md`:

- `src/`: reusable Python code for data generation, analytics, experimentation, prediction, causal estimation, policy optimization, marketplace constraints, and monitoring.
- `sql/`: schema, metrics, cohort, experiment, and point-in-time feature queries.
- `tests/`: pytest tests for transformations, data contracts, leakage, estimators, and optimization correctness.
- `notebooks/`: thin narrative notebooks that call tested code in `src/`.
- `docs/`: project charter, metric definitions, experiment design, model card, and rollout documentation.
- `configs/`: named economic assumptions and policy constraints.
- `data/` and `reports/`: generated or local-only data and figures; raw/interim data should remain gitignored.

Read `project.md` and `Learn_n_build.md` before changing modeling or causal code. Treat Criteo as randomized advertising data, not churn data.

## Build, Test, and Development Commands

The planned project gates are:

```text
make build    # regenerate the small example pipeline and processed features
make test     # run the complete pytest and data-contract suite
```

Run focused checks with `pytest tests/test_features.py -q`. Keep generated datasets, figures, and reports reproducible from a documented seed and configuration.

## Coding Style & Naming Conventions

Use Python 3.11, four-space indentation, type hints, and descriptive `snake_case` names. Keep business assumptions in YAML under `configs/`, not in notebooks or functions. Prefer small, composable functions in `src/`; notebooks should explain results rather than contain core logic. SQL files should declare grain and use clear CTEs.

## Testing Guidelines

Use pytest fixtures with small hand-built inputs. Test schema, nullability, ranges, uniqueness, referential integrity, point-in-time leakage, estimator recovery, and optimizer agreement. Preserve tests that demonstrate failure under confounding or poor overlap. The leakage test must fail if a feature uses an event at or after its decision timestamp.

## Commit & Pull Request Guidelines

No repository Git history is available yet, so no established commit convention can be inferred. Use concise imperative commits such as `add PIT leakage test` or `implement matched-budget baselines`. PRs should explain the decision or artifact changed, list verification commands and results, identify measured/estimated/simulated outputs, and include relevant figures or report previews.

## Research and Reproducibility

Work phase by phase. Validate causal estimators on simulated data with known ground truth before applying them to Criteo. Prefer transparent baselines over opaque complexity, document assumptions and consequences, and preserve negative or inconclusive findings.
