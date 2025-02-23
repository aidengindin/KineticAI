from typing import Optional
from pydantic import BaseModel

class PredictionResponse(BaseModel):
    predicted_time: int
    predicted_power: int

class CPUpdateResponse(BaseModel):
    cp: int
    wp: int
    k: int
