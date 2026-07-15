from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from . import models, schemas, database, redis_client, kafka_consumer

# Create database tables
models.Base.metadata.create_all(bind=database.engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start Kafka Consumer in the background
    kafka_consumer.start_consumer_thread()
    yield
    # Shutdown logic could go here

app = FastAPI(title="Inventory Service API", lifespan=lifespan)

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/inventory", response_model=schemas.InventoryResponse, status_code=201)
def add_inventory(item: schemas.InventoryCreate, db: Session = Depends(database.get_db)):
    # Check if exists
    db_item = db.query(models.Inventory).filter(models.Inventory.product_id == item.product_id).first()
    if db_item:
        db_item.stock += item.stock
    else:
        db_item = models.Inventory(product_id=item.product_id, stock=item.stock)
        db.add(db_item)
    
    db.commit()
    db.refresh(db_item)
    
    # Update Redis cache
    redis_client.set_stock(db_item.product_id, db_item.stock)
    
    return db_item

@app.get("/api/inventory/{product_id}", response_model=schemas.InventoryResponse)
def get_inventory(product_id: str, db: Session = Depends(database.get_db)):
    # 1. Try to get from Redis Cache first
    cached_stock = redis_client.get_stock(product_id)
    if cached_stock is not None:
        print(f"Cache Hit for {product_id}")
        return schemas.InventoryResponse(product_id=product_id, stock=cached_stock)
        
    print(f"Cache Miss for {product_id}, querying Database...")
    # 2. If Cache miss, query Postgres
    db_item = db.query(models.Inventory).filter(models.Inventory.product_id == product_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Product not found")
        
    # 3. Populate Cache for future requests
    redis_client.set_stock(db_item.product_id, db_item.stock)
    
    return db_item
