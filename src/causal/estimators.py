"""Treatment-effect estimators used in the recovery benchmark."""
from __future__ import annotations
import numpy as np
from sklearn.linear_model import LinearRegression

def difference_in_means(y, treatment) -> float:
    y, treatment = np.asarray(y, float), np.asarray(treatment, int)
    return float(y[treatment == 1].mean() - y[treatment == 0].mean())

def inverse_probability_weighted(y, treatment, propensity) -> float:
    y, treatment, propensity = map(np.asarray, (y, treatment, propensity))
    p = np.clip(propensity.astype(float), 1e-3, 1 - 1e-3)
    return float(np.mean(treatment * y / p - (1 - treatment) * y / (1 - p)))

def regression_adjustment(x, y, treatment) -> float:
    x, y, treatment = np.asarray(x), np.asarray(y, float), np.asarray(treatment, int)
    model = LinearRegression().fit(np.column_stack([x, treatment]), y)
    treated, control = np.column_stack([x, np.ones(len(x))]), np.column_stack([x, np.zeros(len(x))])
    return float(np.mean(model.predict(treated) - model.predict(control)))

def doubly_robust(x, y, treatment, propensity=None) -> float:
    x, y, treatment = np.asarray(x), np.asarray(y, float), np.asarray(treatment, int)
    p = np.full(len(y), treatment.mean()) if propensity is None else np.asarray(propensity, float)
    p = np.clip(p, 1e-3, 1 - 1e-3)
    mu0 = LinearRegression().fit(x[treatment == 0], y[treatment == 0])
    mu1 = LinearRegression().fit(x[treatment == 1], y[treatment == 1])
    m0, m1 = mu0.predict(x), mu1.predict(x)
    pseudo = (m1 - m0) + treatment * (y - m1) / p - (1 - treatment) * (y - m0) / (1 - p)
    return float(np.mean(pseudo))
