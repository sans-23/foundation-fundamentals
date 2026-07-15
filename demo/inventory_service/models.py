from sqlalchemy import Column, Integer, String
from .database import Base

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, unique=True, index=True, nullable=False)
    stock = Column(Integer, nullable=False, default=0)
