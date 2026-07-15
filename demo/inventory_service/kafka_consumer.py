import os
import json
import threading
from confluent_kafka import Consumer, Producer, KafkaError
from .database import SessionLocal
from .models import Inventory
from .redis_client import decrement_stock

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
ORDER_TOPIC = "order.created"
ALLOCATED_TOPIC = "stock.allocated"

conf = {
    'bootstrap.servers': KAFKA_BROKER,
    'group.id': 'inventory-service-group',
    'auto.offset.reset': 'earliest'
}

producer_conf = {
    'bootstrap.servers': KAFKA_BROKER,
    'client.id': 'inventory-service-producer'
}
producer = Producer(producer_conf)

def process_order_event(event_data: dict):
    product_id = event_data.get('product_id')
    quantity = event_data.get('quantity')
    order_id = event_data.get('id')
    user_id = event_data.get('user_id')
    
    print(f"Processing stock allocation for Order {order_id}, Product: {product_id}, Qty: {quantity}")
    
    # 1. Optimistically decrement in Redis first (Fast)
    decrement_stock(product_id, quantity)
    
    # 2. Persist to Postgres (Source of Truth)
    db = SessionLocal()
    try:
        inventory_item = db.query(Inventory).filter(Inventory.product_id == product_id).first()
        if inventory_item:
            inventory_item.stock -= quantity
            db.commit()
            print(f"Postgres updated: Product {product_id} stock is now {inventory_item.stock}")
            
            # PUBLISH stock.allocated
            allocated_event = {
                "order_id": order_id,
                "user_id": user_id,
                "product_id": product_id,
                "status": "ALLOCATED"
            }
            producer.produce(
                topic=ALLOCATED_TOPIC,
                key=str(order_id),
                value=json.dumps(allocated_event).encode('utf-8')
            )
            producer.flush(timeout=5)
            print(f"Published stock.allocated for Order {order_id}")
            
        else:
            print(f"Warning: Product {product_id} not found in database!")
    except Exception as e:
        print(f"Database error: {e}")
        db.rollback()
    finally:
        db.close()

def consume_loop():
    consumer = Consumer(conf)
    consumer.subscribe([ORDER_TOPIC])
    print("Kafka Consumer started, listening for 'order.created' events...")

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    print(msg.error())
                    break
            
            event_value = json.loads(msg.value().decode('utf-8'))
            process_order_event(event_value)
            
    except Exception as e:
        print(f"Consumer loop error: {e}")
    finally:
        consumer.close()

def start_consumer_thread():
    thread = threading.Thread(target=consume_loop, daemon=True)
    thread.start()
