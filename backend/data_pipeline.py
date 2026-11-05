"""Kaggle adapter and leakage-safe, time-ordered feature engineering."""
from __future__ import annotations

import hashlib
import copy
from collections import defaultdict, deque
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Iterable

import numpy as np
import pandas as pd

KAGGLE_COLUMNS = {
    "trans_num": "transaction_id", "cc_num": "account_id", "trans_date_trans_time": "transaction_time",
    "amt": "amount", "merchant": "merchant_id", "category": "merchant_category",
    "is_fraud": "label", "lat": "customer_lat", "long": "customer_long",
    "merch_lat": "merchant_lat", "merch_long": "merchant_long",
}

FEATURE_COLUMNS = [
    "card_txn_count_5m", "card_txn_count_1h", "card_txn_count_24h", "card_amount_sum_1h",
    "card_amount_sum_24h", "card_txn_count_7d", "card_avg_amount_7d", "amount_vs_card_avg", "amount_zscore_card", "amount_log",
    "time_since_last_transaction", "is_new_merchant", "is_new_city", "is_new_state",
    "merchant_count_24h", "category_count_24h", "unique_merchant_count_24h", "hour", "day_of_week", "is_weekend", "is_night",
    "hour_sin", "hour_cos", "distance_from_home", "distance_from_last_transaction", "distance_to_merchant",
    "impossible_travel", "merchant_fraud_rate_history", "merchant_txn_count", "category_fraud_rate_history", "global_fraud_rate_history",
    "amount", "merchant_category", "merchant_id",
]

def _stats_default(): return [0, 0]
def _set_default(): return set()

def hash_card(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _clean_text(value: pd.Series, default: str = "unknown") -> pd.Series:
    """Normalize nullable text without creating the literal string ``nan``."""
    result = value.astype("string").fillna(default).str.strip()
    return result.mask(result.eq(""), default).astype(str)


def _require_text(frame: pd.DataFrame, column: str) -> None:
    """Reject missing identifiers that are needed for temporal history."""
    values = frame[column].astype("string")
    missing = values.isna() | values.str.strip().eq("")
    if missing.fillna(True).any():
        raise ValueError(f"missing values in required column: {column}")


def _require_finite(frame: pd.DataFrame, column: str) -> None:
    """Reject missing or non-finite values in required numeric columns."""
    values = pd.to_numeric(frame[column], errors="coerce")
    numeric = values.to_numpy(dtype=float)
    if values.isna().any() or not np.isfinite(numeric).all():
        raise ValueError(f"missing or non-finite values in required column: {column}")
    frame[column] = values

def adapt_kaggle(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.rename(columns=KAGGLE_COLUMNS).copy()
    out = out.drop(columns=[c for c in out.columns if str(c).startswith("Unnamed:")], errors="ignore")
    out = out.drop(columns=["first", "last", "street", "dob", "job", "zip"], errors="ignore")
    required = ["transaction_id", "account_id", "transaction_time", "amount", "merchant_id", "merchant_category"]
    missing = [c for c in required if c not in out]
    if missing:
        raise ValueError(f"missing Kaggle columns: {missing}")
    _require_text(out, "transaction_id")
    _require_text(out, "account_id")
    out["transaction_id"] = _clean_text(out["transaction_id"])
    out["account_id"] = _clean_text(out["account_id"]).map(hash_card)
    out["merchant_id"] = _clean_text(out["merchant_id"])
    out["merchant_category"] = _clean_text(out["merchant_category"])
    out["transaction_time"] = pd.to_datetime(out["transaction_time"], errors="raise")
    if out["transaction_time"].isna().any():
        raise ValueError("missing values in required column: transaction_time")
    for c in ("amount", "customer_lat", "customer_long", "merchant_lat", "merchant_long"):
        if c in out: out[c] = pd.to_numeric(out[c], errors="coerce")
    _require_finite(out, "amount")
    out["customer_city"] = _clean_text(out["city"]) if "city" in out else "unknown"
    out["customer_state"] = _clean_text(out["state"]) if "state" in out else "unknown"
    return out

def adapt_transaction(frame: pd.DataFrame) -> pd.DataFrame:
    if "trans_num" in frame or "cc_num" in frame: return adapt_kaggle(frame)
    out = frame.copy()
    if "transaction_id" in out and not out["transaction_id"].isna().all():
        _require_text(out, "transaction_id")
        out["transaction_id"] = _clean_text(out["transaction_id"])
    else:
        out["transaction_id"] = [f"txn_{position + 1}" for position in range(len(out))]
    account = out.get("account_id", out.get("user_id", pd.Series(["unknown"] * len(out), index=out.index)))
    out["account_id"] = _clean_text(account).map(hash_card)
    out["transaction_time"] = pd.to_datetime(out["transaction_time"], errors="raise")
    if out["transaction_time"].isna().any():
        raise ValueError("missing values in required column: transaction_time")
    out["amount"] = pd.to_numeric(out["amount"], errors="coerce")
    _require_finite(out, "amount")
    def column(name, fallback):
        value = out.get(name, fallback)
        return value if isinstance(value, pd.Series) else pd.Series([value] * len(out), index=out.index)
    out["merchant_id"] = _clean_text(column("merchant_id", column("merchant", "unknown")))
    out["merchant_category"] = _clean_text(column("merchant_category", column("category", "unknown")))
    out["customer_city"] = _clean_text(column("customer_city", column("city", "unknown")))
    out["customer_state"] = _clean_text(column("customer_state", column("state", "unknown")))
    for c in ("customer_lat", "customer_long", "merchant_lat", "merchant_long"):
        out[c] = pd.to_numeric(column(c, np.nan), errors="coerce")
    return out

def _distance(a_lat, a_lon, b_lat, b_lon):
    if any(pd.isna(x) for x in (a_lat, a_lon, b_lat, b_lon)): return 0.0
    p1, p2 = radians(a_lat), radians(b_lat)
    dlat, dlon = radians(b_lat-a_lat), radians(b_lon-a_lon)
    x = sin(dlat/2)**2 + cos(p1)*cos(p2)*sin(dlon/2)**2
    return 3958.8 * 2 * asin(sqrt(min(1, x)))

class FeatureState:
    """Online feature state that can be carried from one temporal window to the next."""
    def __init__(self):
        self.history = defaultdict(deque)
        self.merchant_stats = defaultdict(_stats_default)
        self.category_stats = defaultdict(_stats_default)
        self.global_stats = [0, 0]
        self.seen_merchants = defaultdict(_set_default)
        self.seen_cities = defaultdict(_set_default)
        self.seen_states = defaultdict(_set_default)

    def clone(self):
        return copy.deepcopy(self)

def build_features(rows: pd.DataFrame, labels: Iterable[int] | None = None, progress: bool = False, state: FeatureState | None = None) -> pd.DataFrame:
    data = adapt_transaction(rows)
    data["__row_order"] = np.arange(len(data))
    if labels is not None: data["__label"] = list(labels)
    data = data.sort_values("transaction_time", kind="stable")
    y = data["__label"].tolist() if labels is not None else [None] * len(data)
    if len(y) != len(data): raise ValueError("labels and rows have different lengths")
    state = state or FeatureState()
    history, merchant_stats, category_stats = state.history, state.merchant_stats, state.category_stats
    global_stats = state.global_stats; smoothing = 10.0
    seen_merchants, seen_cities, seen_states = state.seen_merchants, state.seen_cities, state.seen_states
    result = []
    data_total = len(data)
    # Large runs still show regular heartbeat messages without spending time
    # continually writing hundreds of console lines.
    progress_step = 5_000 if data_total <= 100_000 else 25_000
    # Keep this online/stateful loop (so no future transaction leaks into a
    # feature), but derive all window aggregates in one pass over the card
    # history.  The previous version scanned the same deque 10+ times per
    # transaction and used ``iterrows()``, which made full test evaluation
    # look frozen for many minutes.
    five_minutes = pd.Timedelta(minutes=5)
    one_hour = pd.Timedelta(hours=1)
    one_day = pd.Timedelta(days=1)
    seven_days = pd.Timedelta(days=7)
    columns = list(data.columns)
    for position, (row_values, label) in enumerate(zip(data.itertuples(index=False, name=None), y), start=1):
        row = dict(zip(columns, row_values))
        t, card, amount = row["transaction_time"], row["account_id"], float(row["amount"])
        h = history[card]; cutoff = t - seven_days
        while h and h[0][0] < cutoff: h.popleft()

        count_5m = count_1h = count_24h = 0
        sum_1h = sum_24h = total_amount = total_squared = 0.0
        merchant_24h = category_24h = 0
        merchants_24h = set()
        for event_time, event_amount, event_category, event_merchant, _, _ in h:
            total_amount += event_amount
            total_squared += event_amount * event_amount
            age = t - event_time
            if age <= one_day:
                count_24h += 1; sum_24h += event_amount
                merchants_24h.add(event_merchant)
                merchant_24h += int(event_merchant == row["merchant_id"])
                category_24h += int(event_category == row["merchant_category"])
                if age <= one_hour:
                    count_1h += 1; sum_1h += event_amount
                    if age <= five_minutes: count_5m += 1
        avg = total_amount / len(h) if h else amount
        variance = max(total_squared / len(h) - avg * avg, 0.0) if len(h) > 1 else 1.0
        std = np.sqrt(variance) if len(h) > 1 else 1.0
        last = h[-1][0] if h else None
        prior_merchant = merchant_stats[row["merchant_id"]]; prior_category = category_stats[row["merchant_category"]]
        last_loc = h[-1][4:6] if h else (np.nan, np.nan)
        d_home = _distance(row["customer_lat"], row["customer_long"], row["merchant_lat"], row["merchant_long"])
        d_last = _distance(last_loc[0], last_loc[1], row["customer_lat"], row["customer_long"])
        d_merchant = _distance(row["customer_lat"], row["customer_long"], row["merchant_lat"], row["merchant_long"])
        global_rate = global_stats[1] / global_stats[0] if global_stats[0] else 0.0
        merchant_rate = (prior_merchant[1] + smoothing * global_rate) / (prior_merchant[0] + smoothing)
        category_rate = (prior_category[1] + smoothing * global_rate) / (prior_category[0] + smoothing)
        values = dict(card_txn_count_5m=count_5m, card_txn_count_1h=count_1h, card_txn_count_24h=count_24h, card_amount_sum_1h=sum_1h, card_amount_sum_24h=sum_24h, card_txn_count_7d=len(h), card_avg_amount_7d=avg, amount_vs_card_avg=amount/(avg+1e-6), amount_zscore_card=(amount-avg)/(std+1e-6), amount_log=np.log1p(max(amount, 0)), time_since_last_transaction=(t-last).total_seconds() if last else 1e9, is_new_merchant=int(row["merchant_id"] not in seen_merchants[card]), is_new_city=int(row["customer_city"] not in seen_cities[card]), is_new_state=int(row["customer_state"] not in seen_states[card]), merchant_count_24h=merchant_24h, category_count_24h=category_24h, unique_merchant_count_24h=len(merchants_24h), hour=t.hour, day_of_week=t.dayofweek, is_weekend=int(t.dayofweek >= 5), is_night=int(t.hour in [0,1,2,3,4,5]), hour_sin=np.sin(2*np.pi*t.hour/24), hour_cos=np.cos(2*np.pi*t.hour/24), distance_from_home=d_home, distance_from_last_transaction=d_last, distance_to_merchant=d_merchant, impossible_travel=int(d_last > 500 and last is not None and (t-last).total_seconds() < 3600), merchant_fraud_rate_history=merchant_rate, merchant_txn_count=prior_merchant[0], category_fraud_rate_history=category_rate, global_fraud_rate_history=global_rate, amount=amount, merchant_category=str(row["merchant_category"]), merchant_id=str(row["merchant_id"]))
        result.append(values)
        h.append((t, amount, row["merchant_category"], row["merchant_id"], row["customer_lat"], row["customer_long"])); seen_merchants[card].add(row["merchant_id"]); seen_cities[card].add(row["customer_city"]); seen_states[card].add(row["customer_state"])
        merchant_stats[row["merchant_id"]][0] += 1; category_stats[row["merchant_category"]][0] += 1
        if label is not None: merchant_stats[row["merchant_id"]][1] += int(label); category_stats[row["merchant_category"]][1] += int(label)
        if label is not None: global_stats[0] += 1; global_stats[1] += int(label)
        if progress and (position == 1 or position % progress_step == 0 or position == data_total):
            print(f"      features: {position:,}/{data_total:,} ({position / max(data_total, 1):.1%})", flush=True)
    features = pd.DataFrame(result, columns=FEATURE_COLUMNS)
    numeric_columns = features.select_dtypes(include=[np.number]).columns
    numeric_values = features[numeric_columns].to_numpy(dtype=float)
    if not np.isfinite(numeric_values).all():
        invalid = [column for column in numeric_columns if not np.isfinite(features[column].to_numpy(dtype=float)).all()]
        raise ValueError(f"feature engineering produced missing or non-finite values: {invalid}")
    return features.assign(__row_order=data["__row_order"].to_numpy()).sort_values("__row_order").drop(columns="__row_order").reset_index(drop=True)
