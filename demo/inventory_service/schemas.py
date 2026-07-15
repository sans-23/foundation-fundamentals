from pydantic import BaseModel

class InventoryCreate(BaseModel):
    product_id: str
    stock: int

class InventoryResponse(BaseModel):
    product_id: str
    stock: int

    class Config:
        from_attributes = True
