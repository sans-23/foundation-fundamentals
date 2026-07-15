from fastapi import FastAPI
from contextlib import asynccontextmanager
from . import kafka_consumer

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start Kafka Consumer in the background
    kafka_consumer.start_consumer_thread()
    yield

app = FastAPI(title="Notification Service API", lifespan=lifespan)

@app.get("/health")
def health_check():
    return {"status": "healthy"}
