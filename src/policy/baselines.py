"""Matched-population policy constructors."""
from __future__ import annotations
import numpy as np
import pandas as pd

def build_baseline_policy(candidates: pd.DataFrame, name: str, budget: float, seed: int = 2025) -> pd.DataFrame:
    if not {"user_id", "action", "expected_value", "expected_cost"} <= set(candidates.columns): raise ValueError("candidate contract is incomplete")
    rng=np.random.default_rng(seed); users=candidates.user_id.drop_duplicates().to_numpy()
    chosen=[]
    if name == "none": return candidates[candidates.action == "no_offer"].copy()
    if name == "all":
        offered=candidates[candidates.action == "small_offer"].sort_values("user_id").copy()
        selected=offered.iloc[:0].copy()
        used=0.0
        keep=[]
        for row in offered.itertuples():
            if used + row.expected_cost > budget: break
            keep.append(row.Index); used += row.expected_cost
        selected=offered.loc[keep].copy()
    else:
        rank_col={"random":None,"propensity":"propensity_score","uplift":"incremental_conversion","net_value":"expected_value"}.get(name)
        if name not in {"random","propensity","uplift","net_value"}: raise ValueError(f"unknown policy {name}")
        offered=candidates[candidates.action != "no_offer"].copy()
        if rank_col is None: offered=offered.iloc[rng.permutation(len(offered))]
        else: offered=offered.sort_values(rank_col, ascending=False)
        used=0.0; seen=set()
        for row in offered.itertuples():
            if row.user_id in seen or used + row.expected_cost > budget: continue
            chosen.append(row.Index); seen.add(row.user_id); used += row.expected_cost
        selected=candidates.loc[chosen].copy()
    selected=selected.sort_values(["user_id","expected_value"], ascending=[True,False]).drop_duplicates("user_id")
    missing=sorted(set(users)-set(selected.user_id))
    if missing: selected=pd.concat([selected, candidates[(candidates.user_id.isin(missing)) & (candidates.action=="no_offer")]], ignore_index=True)
    return selected
