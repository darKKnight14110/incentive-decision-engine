from pathlib import Path
import yaml

from src.reporting.metric_tree import build_metric_tree

ROOT = Path(__file__).parents[1]


def load_yaml(relative_path: str) -> dict:
    with (ROOT / relative_path).open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_actions_and_windows_are_aligned() -> None:
    base = load_yaml("configs/base.yaml")
    assert set(base["actions"]) == {"no_offer", "small_offer", "large_offer"}
    assert base["project"]["outcome_window_days"] == 14
    assert base["project"]["attribution_window_days"] == 14


def test_placeholders_have_sensitivity_ranges() -> None:
    economics = load_yaml("configs/base.yaml")["economics"]
    margin = economics["contribution_margin_rate"]
    assert margin["sensitivity"][0] < margin["value"] < margin["sensitivity"][1]
    for action in ("small", "large"):
        item = economics["offer_redemption_rate"][action]
        assert item["sensitivity"][0] < item["value"] < item["sensitivity"][1]


def test_metric_register_has_complete_anatomy_and_labels() -> None:
    text = (ROOT / "docs/metric_definition.md").read_text(encoding="utf-8")
    assert "| Metric | Role | Numerator | Denominator | Grain | Window | Filter |" in text
    assert "Incremental contribution margin per eligible customer" in text
    assert all(label in text for label in ("Measured", "Estimated", "Simulated"))


def test_contact_frequency_is_hard_constraint() -> None:
    policy = load_yaml("configs/policy_constraints.yaml")
    assert policy["eligibility"]["contact_cooldown_days"] == 14
    assert policy["constraints"]["contact_frequency_is_hard_constraint"] is True


def test_metric_tree_can_be_rebuilt(tmp_path: Path) -> None:
    target = build_metric_tree(tmp_path / "metric_tree.png")
    assert target.is_file() and target.stat().st_size > 10_000
