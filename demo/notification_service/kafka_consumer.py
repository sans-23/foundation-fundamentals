import os
import json
import threading
from confluent_kafka import Consumer, KafkaError
from .redis_dedup import is_duplicate

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
ALLOCATED_TOPIC = "stock.allocated"

conf = {
    'bootstrap.servers': KAFKA_BROKER,
    'group.id': 'notification-service-group',
    'auto.offset.reset': 'earliest'
}

def send_notification(user_id: str, order_id: str, product_id: str):
    # Simulated Notification
    print(f"\n======================================")
    print(f"📧 EMAIL SENT TO USER: {user_id}")
    print(f"Subject: Order {order_id} Confirmed!")
    print(f"Body: Great news! We have successfully allocated stock for your product ({product_id}).")
    print(f"======================================\n")

def process_allocated_event(event_data: dict, partition: int, offset: int):
    order_id = event_data.get('order_id')
    user_id = event_data.get('user_id')
    product_id = event_data.get('product_id')
    
    # We use the order_id (and specific status) as our unique idempotency key
    # If Kafka guarantees unique event UUIDs, we could use that instead.
    event_key = f"stock_allocated_{order_id}"
    
    print(f"Received event from Partition {partition} Offset {offset}: {event_key}")
    
    # IDEMPOTENCY CHECK
    if is_duplicate(event_key):
        print(f"⚠️ DEDUPLICATION ALERT: Event {event_key} has already been processed! Skipping.")
        return
        
    print(f"✅ Event {event_key} is new. Proceeding to send notification...")
    send_notification(user_id, order_id, product_id)

def consume_loop():
    consumer = Consumer(conf)
    consumer.subscribe([ALLOCATED_TOPIC])
    print("Notification Consumer started, listening for 'stock.allocated' events...")

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
            process_allocated_event(event_value, msg.partition(), msg.offset())
            
    except Exception as e:
        print(f"Consumer loop error: {e}")
    finally:
        consumer.close()

def start_consumer_thread():
    thread = threading.Thread(target=consume_loop, daemon=True)
    thread.start()
