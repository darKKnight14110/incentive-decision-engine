"""Lightweight decision dashboard for generated portfolio reports."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
table=ROOT/"reports"/"policy_comparison.csv"
policy_table=ROOT/"reports"/"policy_results.csv"
claim_file=ROOT/"reports"/"business_case_claim.json"
st.set_page_config(page_title="Increment decision engine", layout="wide")
st.title("Increment: promotion allocation")
st.caption("Synthetic decision dashboard. Values are estimated/simulated, not realized business impact.")
if not table.exists():
    st.warning("Run `make build` first to generate the smoke artifacts.")
else:
    data=pd.read_csv(table)
    if claim_file.exists():
        import json
        claim=json.loads(claim_file.read_text(encoding="utf-8"))
        st.info(
            f"Canonical 50% scenario: optimizer ₹{claim['optimized_expected_value_inr']:,.0f} "
            f"vs random ₹{claim['random_expected_value_inr']:,.0f}; "
            f"difference ₹{claim['incremental_value_vs_random_inr_total']:,.0f} total "
            f"(95% interval ₹{claim['ci_low_inr_per_eligible_user']:.2f} to "
            f"₹{claim['ci_high_inr_per_eligible_user']:.2f} per user)."
        )
    budget=st.slider("Budget (INR)", float(data.budget_inr.min()), float(data.budget_inr.max()), float(data.budget_inr.iloc[min(2,len(data)-1)]))
    row=data.iloc[(data.budget_inr-budget).abs().argmin()]
    c1,c2,c3=st.columns(3); c1.metric("Expected net value",f"₹{row.expected_value:,.0f}"); c2.metric("Spend",f"₹{row.expected_cost:,.0f}"); c3.metric("Marginal budget proxy",f"₹{row.shadow_price_proxy:,.2f}")
    if policy_table.exists():
        policies=pd.read_csv(policy_table)
        pivot=policies.pivot_table(index="budget_inr",columns="policy",values="expected_value",aggfunc="sum")
        st.subheader("Matched-budget policy comparison")
        st.line_chart(pivot)
        selected=policies.iloc[(policies.budget_inr-budget).abs().argmin()]
        st.caption(f"At the nearest budget point, the selected row is **{selected.policy}**. All policies use the same 500-user synthetic population.")
    else:
        st.line_chart(data.set_index("budget_inr")[["expected_value"]])
    for name in ("profit_vs_budget.png","qini_comparison.png","uplift_deciles.png"):
        path=ROOT/"reports"/"figures"/name
        if path.exists(): st.image(str(path), caption=name.replace("_"," ").title())
