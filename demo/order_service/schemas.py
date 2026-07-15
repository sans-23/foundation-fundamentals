from pydantic import BaseModel
from typing import Optional
from .models import OrderStatus

class OrderCreate(BaseModel):
    product_id: str
    quantity: int
    total_price: float

class OrderResponse(BaseModel):
    id: int
    user_id: str
    product_id: str
    quantity: int
    total_price: float
    status: OrderStatus

    class Config:
        from_attributes = True
