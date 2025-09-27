from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

class DeviceIn(BaseModel):
    device_id: str
    device_fingerprint: Optional[str] = None

class TransactionIn(BaseModel):
    account_number: str
    amount: float
    currency: Optional[str] = "INR"
    merchant: Optional[str] = None
    device: Optional[DeviceIn] = None
    metadata: Optional[Dict] = {}

class TransactionOut(BaseModel):
    id: str
    account_number: str
    amount: float
    score: float
    verdict: str
    timestamp: datetime
