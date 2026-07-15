import os
import json
from confluent_kafka import Producer

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
ORDER_TOPIC = "order.created"

conf = {
    'bootstrap.servers': KAFKA_BROKER,
    'client.id': 'order-service-producer'
}

producer = None

def get_producer():
    global producer
    if producer is None:
        try:
            producer = Producer(conf)
        except Exception as e:
            print(f"Failed to connect to Kafka: {e}")
    return producer

def publish_order_created(order_dict: dict):
    p = get_producer()
    if p:
        try:
            # Produce message
            p.produce(
                topic=ORDER_TOPIC,
                key=str(order_dict.get('id')),
                value=json.dumps(order_dict).encode('utf-8')
            )
            # Flush is synchronous, in high-throughput use poll() instead.
            p.flush(timeout=5)
            print(f"Published order {order_dict.get('id')} to Kafka")
        except Exception as e:
            print(f"Failed to publish to Kafka: {e}")
