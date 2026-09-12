"""Small deterministic monitoring metrics."""
from __future__ import annotations
import numpy as np

def population_stability_index(reference, current, bins: int = 10) -> float:
    reference, current=np.asarray(reference,float), np.asarray(current,float)
    edges=np.unique(np.quantile(reference, np.linspace(0,1,bins+1)))
    if len(edges)<2: return 0.0
    r,_=np.histogram(reference, bins=edges); c,_=np.histogram(current,bins=edges)
    rp=(r+1e-6)/(r.sum()+1e-6*len(r)); cp=(c+1e-6)/(c.sum()+1e-6*len(c))
    return float(np.sum((cp-rp)*np.log(cp/rp)))

def calibration_drift(expected, observed) -> float:
    expected, observed=np.asarray(expected,float), np.asarray(observed,float)
    return float(np.mean((expected-observed)**2))

def policy_mix_drift(reference, current) -> float:
    keys=set(reference)|set(current); return float(sum(abs(reference.get(k,0)-current.get(k,0)) for k in keys)/2)
