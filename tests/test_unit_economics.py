from pathlib import Path

import pytest
import yaml

from src.economics.unit_economics import (
    cost_per_incremental_order,
    expected_offer_cost,
    incremental_value,
    return_on_investment,
)

ROOT = Path(__file__).parents[1]


def test_redemption_cost_only_charges_redeemed_offer_value() -> None:
    assert expected_offer_cost(75, 0.60, "redemption") == pytest.approx(45)


def test_exposure_cost_charges_every_offer_shown() -> None:
    assert expected_offer_cost(75, 0.60, "exposure") == pytest.approx(75)


def test_incremental_value_has_margin_lift_minus_offer_cost() -> None:
    value = incremental_value(
        predicted_incremental_conversion=0.03,
        expected_contribution_margin=110,
        face_value=75,
        redemption_rate=0.60,
        cost_accounting_mode="redemption",
    )
    assert value == pytest.approx(-41.70)


def test_cpio_and_roi_are_based_on_incremental_orders() -> None:
    offer_cost = expected_offer_cost(75, 0.60, "redemption")
    assert cost_per_incremental_order(offer_cost, 0.03) == pytest.approx(1500)
    assert return_on_investment(0.03 * 110 - offer_cost, offer_cost) == pytest.approx(
        -0.9266666667
    )


@pytest.mark.parametrize("incremental_orders", [0, -0.01])
def test_efficiency_metrics_are_suppressed_without_positive_incremental_orders(
    incremental_orders: float,
) -> None:
    assert cost_per_incremental_order(45, incremental_orders) is None


def test_zero_cost_roi_is_suppressed() -> None:
    assert return_on_investment(10, 0) is None


def test_base_config_declares_named_cost_accounting_mode() -> None:
    with (ROOT / "configs/base.yaml").open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    mode = config["economics"]["offer_cost_accounting_mode"]
    assert mode in {"exposure", "redemption"}
