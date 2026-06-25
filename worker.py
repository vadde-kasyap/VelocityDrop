import asyncio
import sys
import multiprocessing
import argparse
import aio_pika
import redis
import json
from sqlalchemy import text
from database import SessionLocal, Order, Wallet, Product

# Force UTF-8 output so Rs symbol and emoji render correctly on Windows terminals
sys.stdout.reconfigure(encoding='utf-8')

RABBITMQ_URL = "amqp://guest:guest@localhost/"

# Each spawned process creates its own Redis connection (not shared across processes)
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)


# ---------------------------------------------------------
# Core Order Logic — pure synchronous function
# Runs inside asyncio.to_thread() so it NEVER blocks the event loop.
# Each concurrent call gets its own DB session — fully thread-safe.
# ---------------------------------------------------------
def process_order(order_data: dict):
    user_id        = order_data['user_id']
    product_name   = order_data['product_name']
    idempotency_key = order_data['idempotency_key']
    quantity       = order_data['quantity']

    # 1. Idempotency check — prevent duplicate charges
    redis_idem_key = f"idempotent_txn:{idempotency_key}"
    if redis_client.exists(redis_idem_key):
        print(f"⚠️  Duplicate: {idempotency_key[:8]} — ignored.")
        return

    redis_client.set(redis_idem_key, "processing", ex=86400)
    db = SessionLocal()

    try:
        # 2. Fetch product from Postgres
        product = db.query(Product).filter(Product.name == product_name).first()

        if not product:
            print(f"❌ FAILED: '{product_name}' not found in database.")
            redis_client.set(redis_idem_key, "failed_invalid_data", ex=86400)
            return

        total_cost = round(product.price * quantity, 2)

        # 3. ATOMIC Funds Deduction (Fixing the Wallet Race Condition)
        # We UPDATE and check balance in a single atomic SQL transaction.
        deduct_sql = text("""
            UPDATE wallets 
            SET balance = balance - :cost 
            WHERE user_id = :uid AND balance >= :cost 
            RETURNING balance
        """)
        
        result = db.execute(deduct_sql, {"cost": total_cost, "uid": user_id}).fetchone()
        
        if not result:
            print(f"❌ INSUFFICIENT FUNDS: {user_id} tried to buy {product_name}")
            db.add(Order(
                user_id=user_id, product_name=product_name,
                quantity=quantity, status="failed_funds"
            ))
            db.commit()
            redis_client.set(redis_idem_key, "failed_funds", ex=86400)
            return
            
        new_balance = round(result[0], 2)

        # 4. Atomic Redis inventory decrement
        inventory_key  = f"inventory:{product_name}"
        stock_remaining = redis_client.decrby(inventory_key, quantity)

        if stock_remaining >= 0:
            # 5. SUCCESS (Saga Pattern: Try/Except to prevent Orphaned Inventory)
            try:
                db.add(Order(
                    user_id=user_id, product_name=product_name,
                    quantity=quantity, status="success"
                ))
                db.commit()
                print(
                    f"✅ SUCCESS: {user_id} × {quantity} {product_name} | "
                    f"Wallet: ₹{new_balance} | Stock left: {stock_remaining}"
                )
                redis_client.set(redis_idem_key, "success", ex=86400)
            except Exception as e:
                # 6. DISTRIBUTED ROLLBACK: If Postgres crashes exactly now, refund Redis!
                db.rollback()
                redis_client.incrby(inventory_key, quantity)
                # We raise the exception so RabbitMQ does NOT ack the message, preventing order loss.
                raise e

        else:
            # 7. Overdraw rollback — stock hit zero, refund Redis AND the Wallet
            redis_client.incrby(inventory_key, quantity)
            
            # Refund the wallet since we already deducted it in Step 3!
            refund_sql = text("UPDATE wallets SET balance = balance + :cost WHERE user_id = :uid")
            db.execute(refund_sql, {"cost": total_cost, "uid": user_id})
            
            print(f"❌ SOLD OUT: {user_id} wanted {quantity} × {product_name}")
            db.add(Order(
                user_id=user_id, product_name=product_name,
                quantity=quantity, status="failed_sold_out"
            ))
            db.commit()
            redis_client.set(redis_idem_key, "failed_sold_out", ex=86400)

    except Exception as outer_e:
        # Pass the exception up so the message is not acked by RabbitMQ
        raise outer_e
    finally:
        db.close()


# ---------------------------------------------------------
# Async message handler
# asyncio.to_thread() offloads the blocking DB work to a thread-pool,
# freeing the event loop to immediately accept the next message.
# This is what makes prefetch_count > 1 actually useful.
# ---------------------------------------------------------
async def on_message(message: aio_pika.IncomingMessage):
    async with message.process():
        order_data = json.loads(message.body)
        await asyncio.to_thread(process_order, order_data)


# ---------------------------------------------------------
# Per-process async entry point
# ---------------------------------------------------------
async def run_worker_async(worker_id: int, prefetch: int):
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel    = await connection.channel()

    # prefetch_count tells RabbitMQ: "send me up to N unacknowledged messages at once"
    # Combined with asyncio.to_thread, each worker truly processes N orders in parallel
    await channel.set_qos(prefetch_count=prefetch)

    queue = await channel.declare_queue("checkout_queue", durable=True)
    print(f"👷 Worker-{worker_id} online | prefetch={prefetch} | waiting for orders...")
    await queue.consume(on_message)
    await asyncio.Future()  # run forever


def start_worker(worker_id: int, prefetch: int):
    """
    Entry point for each spawned process.
    Each process has its own event loop — fully isolated.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # Reconfigure stdout per-process so emoji/Rs symbol work on Windows
    sys.stdout.reconfigure(encoding='utf-8')
    asyncio.run(run_worker_async(worker_id, prefetch))


# ---------------------------------------------------------
# Main — spawn N worker processes, each with M prefetch slots
# Usage:
#   python worker.py                      # 4 workers, 10 prefetch each (default)
#   python worker.py --workers 2 --prefetch 5
#   python worker.py --workers 1 --prefetch 1  # original single-worker mode
# ---------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VelocityDrop Checkout Worker")
    parser.add_argument(
        "--workers",  type=int, default=2,
        help="Number of worker processes to spawn (default: 2)"
    )
    parser.add_argument(
        "--prefetch", type=int, default=5,
        help="Concurrent messages each worker handles at once (default: 5)"
    )
    args = parser.parse_args()

    total_capacity = args.workers * args.prefetch
    print(
        f"\n🚀 VelocityDrop Worker Pool\n"
        f"   Processes : {args.workers}\n"
        f"   Prefetch  : {args.prefetch} per worker\n"
        f"   Capacity  : {total_capacity} concurrent orders\n"
    )

    if args.workers == 1:
        # Single process — run directly without spawning overhead
        start_worker(1, args.prefetch)
    else:
        processes = []
        for i in range(1, args.workers + 1):
            p = multiprocessing.Process(
                target=start_worker,
                args=(i, args.prefetch),
                daemon=True
            )
            p.start()
            processes.append(p)
            print(f"   ✓ Worker-{i} spawned (PID {p.pid})")

        print(f"\n   All {args.workers} workers running. Press Ctrl+C to stop.\n")

        try:
            for p in processes:
                p.join()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down all workers gracefully...")
            for p in processes:
                p.terminate()
            for p in processes:
                p.join()
            print("✅ All workers stopped.")