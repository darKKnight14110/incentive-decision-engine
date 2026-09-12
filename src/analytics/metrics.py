from __future__ import annotations
import pandas as pd

def funnel_metrics(sessions: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    users = sessions.user_id.nunique() if "user_id" in sessions else 0
    cart = sessions.loc[sessions.cart_ts.notna(), "user_id"].nunique() if "cart_ts" in sessions else 0
    checkout = sessions.loc[sessions.checkout_ts.notna(), "user_id"].nunique() if "checkout_ts" in sessions else 0
    completed = orders.loc[orders.status.eq("completed"), "user_id"].nunique() if {"status","user_id"} <= set(orders.columns) else 0
    return pd.DataFrame({"stage":["session","cart","checkout","completed_order"],"users":[users,cart,checkout,completed]})

def lifecycle_counts(features: pd.DataFrame, column: str = "lifecycle_state") -> pd.DataFrame:
    if column not in features: return pd.DataFrame(columns=[column,"users"])
    return features.groupby(column, dropna=False).size().reset_index(name="users")
