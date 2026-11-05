from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


def generate(count: int = 10000, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    methods = ["Visa", "MasterCard", "PayPal", "Crypto"]
    devices = ["Mobile", "Desktop", "Tablet"]
    countries = ["USA", "UK", "India", "Germany", "Brazil", "Russia", "China"]
    rows = []
    for _ in range(count):
        amount = round(rng.uniform(5, 5000), 2)
        hour = rng.randrange(24)
        method = rng.choice(methods)
        device = rng.choice(devices)
        country = rng.choice(countries)
        age = rng.randint(18, 75)
        suspicious = (amount > 3500) + (hour in {0, 1, 2, 3, 4}) + (method == "Crypto") + (device == "Tablet") + (country in {"Russia", "China"})
        # Keep the positive class realistic while preserving learnable signals.
        fraud = int(suspicious >= 2 and rng.random() < 0.15 or rng.random() < 0.004)
        moment = datetime(2025, 1, 1) + timedelta(days=rng.randrange(365), hours=hour, minutes=rng.randrange(60))
        rows.append({"user_id": rng.randint(1000, 9999), "age": age, "amount": amount, "payment_method": method, "device": device, "country": country, "transaction_time": moment, "is_fraud": fraud})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/training_data.csv")
    parser.add_argument("--count", type=int, default=10000)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame = generate(args.count)
    frame.to_csv(output, index=False)
    print(f"saved {len(frame)} rows to {output} (fraud_rate={frame.is_fraud.mean():.3f})")
