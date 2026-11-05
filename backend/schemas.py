from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Transaction(BaseModel):
    user_id: int = Field(default=1, ge=1)
    age: int = Field(default=35, ge=18, le=120)
    amount: float = Field(gt=0)
    payment_method: str = Field(default="unknown", min_length=1)
    device: str = Field(default="unknown", min_length=1)
    country: str = Field(default="unknown", min_length=1)
    transaction_time: datetime
    transaction_id: Optional[str] = None
    account_id: Optional[str] = None
    merchant_id: Optional[str] = None
    merchant_category: Optional[str] = None
    customer_lat: Optional[float] = None
    customer_long: Optional[float] = None
    merchant_lat: Optional[float] = None
    merchant_long: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None

    @field_validator("payment_method", "device", "country")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class Prediction(BaseModel):
    user_id: int
    fraud_probability: float = Field(ge=0, le=1)
    anomaly: bool
    risk_score: float = Field(ge=0, le=100)
    risk_level: str
    reasons: List[str]
    decision: str = "allow"
    threshold_profile: str = "cost_optimal"


class BatchPrediction(BaseModel):
    count: int
    predictions: List[Prediction]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
