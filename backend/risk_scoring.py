from __future__ import annotations


def score(probability: float, anomaly: bool, amount: float, *, reasons: list[str] | None = None, anomaly_score: float = 0.0, threshold: float = .5, profile: str = "balanced") -> dict:
    # Probability is primary; anomaly and unusually large amounts add explainable signal.
    risk = (0.75 * probability + 0.25 * max(anomaly_score, float(anomaly))) * 100
    risk = round(min(100.0, max(0.0, risk)), 2)
    if risk >= 80:
        level = "Critical"
    elif risk >= 60:
        level = "High"
    elif risk >= 30:
        level = "Medium"
    else:
        level = "Low"
    decision = "block" if profile == "strict" and probability >= threshold else ("manual_review" if probability >= threshold else "allow")
    return {"risk_score": risk, "risk_level": level, "reasons": reasons or [], "decision": decision, "threshold_profile": profile}
