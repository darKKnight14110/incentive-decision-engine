from __future__ import annotations
import pandas as pd

def cohort_retention(users: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    if not {"user_id","signup_ts"} <= set(users.columns) or not {"user_id","order_ts"} <= set(orders.columns):
        raise ValueError("users and orders must contain user_id and timestamps")
    signup=users[["user_id","signup_ts"]].copy(); signup["cohort_week"]=pd.to_datetime(signup.signup_ts,utc=True).dt.to_period("W").astype(str)
    merged=orders[["user_id","order_ts"]].merge(signup,on="user_id",how="inner"); merged["weeks_since_signup"]=((pd.to_datetime(merged.order_ts,utc=True)-pd.to_datetime(merged.signup_ts,utc=True)).dt.days//7).clip(lower=0)
    return merged.groupby(["cohort_week","weeks_since_signup"]).user_id.nunique().reset_index(name="retained_users")
