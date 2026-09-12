"""Power and minimum-detectable-effect helpers."""
from __future__ import annotations
from dataclasses import dataclass
from scipy.stats import norm

@dataclass(frozen=True)
class PowerResult:
    mde: float
    power: float
    alpha: float
    treated_n: int
    control_n: int

def minimum_detectable_effect(treated_n: int, control_n: int, outcome_rate: float, alpha: float = 0.05, power: float = 0.8) -> float:
    if min(treated_n, control_n) < 2 or not 0 < outcome_rate < 1:
        raise ValueError("sample sizes must be >=2 and outcome_rate must be in (0, 1)")
    variance = outcome_rate * (1 - outcome_rate) * (1 / treated_n + 1 / control_n)
    return float((norm.ppf(1 - alpha / 2) + norm.ppf(power)) * variance**0.5)

def power_for_effect(effect: float, treated_n: int, control_n: int, outcome_rate: float, alpha: float = 0.05) -> PowerResult:
    if effect < 0:
        raise ValueError("effect must be non-negative")
    mde = minimum_detectable_effect(treated_n, control_n, outcome_rate, alpha)
    se = (outcome_rate * (1 - outcome_rate) * (1 / treated_n + 1 / control_n)) ** 0.5
    critical = norm.ppf(1 - alpha / 2)
    z = effect / se
    power = float(norm.cdf(-critical - z) + 1 - norm.cdf(critical - z))
    return PowerResult(mde, power, alpha, treated_n, control_n)
