from typing import Optional
from pydantic import BaseModel

class RacePrediction(BaseModel):
    user_id: str
    race_id: Optional[str] = None
    cp: int
    running_effectiveness: float
    riegel_exponent: float
    w_prime: int
