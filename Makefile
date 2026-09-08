.PHONY: build test

build:
	python -m src.reporting.metric_tree
	python -m src.data.generate_marketplace --output-dir data/raw
	python -m src.data.build_features --raw-dir data/raw --output-path data/processed/eligible_users.parquet --quality-report data/processed/data_quality_issues.csv

test:
	python -m pytest -q
