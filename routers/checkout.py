from fastapi import APIRouter, Header, Request
import uuid
import json
import aio_pika
from schemas import OrderRequest

router = APIRouter()

@router.post("/checkout", status_code=202)
async def process_checkout(request: Request, order: OrderRequest, idempotency_key: str = Header(None)):
    if not idempotency_key:
        idempotency_key = str(uuid.uuid4())

    payload = {
        "idempotency_key": idempotency_key,
        "user_id": order.user_id,
        "product_name": order.product_name,
        "quantity": order.quantity,
        "status": "pending"
    }

    channel = request.app.state.rabbitmq_channel
    message = aio_pika.Message(
        body=json.dumps(payload).encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT 
    )
    
    await channel.default_exchange.publish(
        message,
        routing_key="checkout_queue"
    )

    return {
        "status": "accepted",
        "message": "You are in line! Your order is being processed.",
        "idempotency_key": idempotency_key
    }
