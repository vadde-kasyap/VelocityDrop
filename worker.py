import asyncio
import sys
import aio_pika
import redis
import json
from database import SessionLocal, Order, Wallet, Product

# Force UTF-8 output so the Rs symbol and emoji render correctly on Windows (cp1252) terminals
sys.stdout.reconfigure(encoding='utf-8')

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

async def process_message(message: aio_pika.IncomingMessage):
    async with message.process():
        order_data = json.loads(message.body)
        user_id = order_data['user_id']
        product_name = order_data['product_name']
        idempotency_key = order_data['idempotency_key']
        quantity = order_data['quantity']
        
        # 1. Idempotency Check (Prevent duplicate charges)
        redis_idem_key = f"idempotent_txn:{idempotency_key}"
        if redis_client.exists(redis_idem_key):
            print(f"⚠️ Duplicate request detected for {idempotency_key}. Ignoring.")
            return

        # Lock the Transaction Key in Redis
        redis_client.setex(redis_idem_key, 86400, "processing")

        db = SessionLocal()

        try:
            # 2. Check Wallet and Product Price
            wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
            product = db.query(Product).filter(Product.name == product_name).first()

            if not wallet or not product:
                print(f"❌ FAILED: User '{user_id}' or Product '{product_name}' not found in database.")
                redis_client.setex(redis_idem_key, 86400, "failed_invalid_data")
                return

            total_cost = round(product.price * quantity, 2)

            # 3. VERIFY FUNDS FIRST (Don't lock inventory if they can't pay!)
            # Round the DB balance here so dirty legacy floats never surface in logs or comparisons
            wallet.balance = round(wallet.balance, 2)

            if wallet.balance < total_cost:
                print(f"❌ FAILED: {user_id} has Insufficient Funds. Need ₹{total_cost}, has ₹{wallet.balance}")
                
                failed_order = Order(
                    user_id=user_id, product_name=product_name, quantity=quantity, status="failed_funds"
                )
                db.add(failed_order)
                db.commit()
                redis_client.setex(redis_idem_key, 86400, "failed_funds")
                return

# 4. Funds are good. Now hit the high-speed Redis lock with dynamic quantity!
            inventory_key = f"inventory:{product_name}"
            # Use DECRBY instead of DECR to subtract the exact cart size
            stock_remaining = redis_client.decrby(inventory_key, quantity)

            if stock_remaining >= 0:
                # 5. SUCCESS! Deduct money and save the final order
                # BUG FIX: round to 2 decimal places to eliminate floating-point noise
                # (e.g. 171.88999999999987 becomes 171.89)
                wallet.balance = round(wallet.balance - total_cost, 2)
                
                new_order = Order(
                    user_id=user_id, product_name=product_name, quantity=quantity, status="success"
                )
                db.add(new_order)
                db.commit()
                
                print(f"✅ SUCCESS: {user_id} bought {quantity} {product_name}(s). Remaining Wallet: ₹{wallet.balance}. Stock left: {stock_remaining}")
                redis_client.setex(redis_idem_key, 86400, "success")
                
            else:
                # 6. OVERDRAW ROLLBACK
                # They tried to buy more than we have left! We must put the items BACK.
                redis_client.incrby(inventory_key, quantity)
                
                print(f"❌ FAILED: {user_id} tried to buy {quantity} {product_name}(s), but there wasn't enough stock.")
                
                failed_order = Order(
                    user_id=user_id, product_name=product_name, quantity=quantity, status="failed_sold_out"
                )
                db.add(failed_order)
                db.commit()
                redis_client.setex(redis_idem_key, 86400, "failed_sold_out")

        finally:
            # Always ensure the database connection closes
            db.close()

async def main():
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    channel = await connection.channel()
    queue = await channel.declare_queue("checkout_queue", durable=True)
    
    print("👷 Worker booted up. Processing orders and wallet deductions...")
    await queue.consume(process_message)
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())