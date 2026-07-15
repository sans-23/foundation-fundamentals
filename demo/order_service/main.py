from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from . import models, schemas, database, security, kafka_publisher

# Create database tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Order Service API")

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/orders", response_model=schemas.OrderResponse, status_code=201)
def create_order(
    order: schemas.OrderCreate, 
    db: Session = Depends(database.get_db),
    user_payload: dict = Depends(security.verify_token)
):
    # Extract user ID from the JWT payload ('sub' claim is standard for user ID)
    user_id = user_payload.get("sub", "unknown")
    
    # Save to database
    db_order = models.Order(
        user_id=user_id,
        product_id=order.product_id,
        quantity=order.quantity,
        total_price=order.total_price
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    # Convert ORM model to Pydantic dict for JSON serialization
    # Pydantic v2 requires model_validate instead of from_orm
    order_dict = schemas.OrderResponse.model_validate(db_order).model_dump()
    
    # Publish to Kafka (Fire and Forget)
    kafka_publisher.publish_order_created(order_dict)
    
    return db_order
