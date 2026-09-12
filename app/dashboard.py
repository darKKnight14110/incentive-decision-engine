"""Lightweight decision dashboard for generated portfolio reports."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
table=ROOT/"reports"/"policy_comparison.csv"
st.set_page_config(page_title="Increment decision engine", layout="wide")
st.title("Increment: promotion allocation")
st.caption("Synthetic decision dashboard. Values are estimated/simulated, not realized business impact.")
if not table.exists():
    st.warning("Run `make build` first to generate the smoke artifacts.")
else:
    data=pd.read_csv(table)
    budget=st.slider("Budget (INR)", float(data.budget_inr.min()), float(data.budget_inr.max()), float(data.budget_inr.iloc[min(2,len(data)-1)]))
    row=data.iloc[(data.budget_inr-budget).abs().argmin()]
    c1,c2,c3=st.columns(3); c1.metric("Expected net value",f"₹{row.expected_value:,.0f}"); c2.metric("Spend",f"₹{row.expected_cost:,.0f}"); c3.metric("Marginal budget proxy",f"₹{row.shadow_price_proxy:,.2f}")
    st.line_chart(data.set_index("budget_inr")[["expected_value"]])
    for name in ("profit_vs_budget.png","qini_comparison.png","uplift_deciles.png"):
        path=ROOT/"reports"/"figures"/name
        if path.exists(): st.image(str(path), caption=name.replace("_"," ").title())
