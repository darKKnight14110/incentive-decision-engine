.PHONY: build test

build:
	python -m src.reporting.metric_tree
	python -m src.data.generate_marketplace --output-dir data/raw
	python -m src.data.build_features --raw-dir data/raw --output-path data/processed/eligible_users.parquet --quality-report data/processed/data_quality_issues.csv
	python -m src.data.validate_data --raw-dir data/raw --report-path data/processed/data_contract_report.csv

test:
	python -m pytest -q
