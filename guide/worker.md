# A Beginner's Guide to `worker.py` (The Heavy Lifter)

In our architecture guide (`arc.md`), we talked about how `main.py` is simply the cashier at a fast-food restaurant. It takes your order, tosses the ticket into a bin (RabbitMQ), and instantly says "Got it!" so the line keeps moving.

The `worker.py` file is the **Kitchen Staff**. It works entirely in the background. It never talks to the user's browser. Its only job is to pull tickets out of the RabbitMQ bin, do the heavy math, and update the database.

Let's break down exactly how this background worker operates!

---

## 1. Bypassing the "GIL" (Multi-Processing)

Python has a famous limitation called the **Global Interpreter Lock (GIL)**. Because of the GIL, a normal Python script can only do *one thing at an exact millisecond*. It cannot do true multi-tasking.

If we have 1,000 orders waiting in the queue, one Python worker will be too slow. To fix this, look at the very bottom of `worker.py`:

```python
if __name__ == "__main__":
    ...
    processes = []
    for _ in range(args.workers):
        p = multiprocessing.Process(target=worker_main, args=(args.prefetch,))
        p.start()
        processes.append(p)
```

Instead of running one worker, we use the `multiprocessing` library to spawn **clones**. If we set `--workers 2`, the computer literally starts two separate Python programs in the background. Because they are separate programs, they bypass the GIL entirely and process orders truly in parallel!

---

## 2. RabbitMQ and "Prefetch"

Once a worker starts, it connects to the RabbitMQ waiting line. But instead of grabbing one order ticket, walking to the kitchen, and coming back, it uses a trick called **Prefetch**:

```python
await channel.set_qos(prefetch_count=prefetch_limit)
```

If we set `prefetch_limit` to 5, the worker grabs 5 tickets at once. This drastically reduces the time wasted walking back and forth to RabbitMQ. 

Because we have 2 workers grabbing 5 tickets each, our system is processing **10 orders concurrently** at any given moment!

---

## 3. The 4 Steps of Processing an Order

When a worker grabs an order ticket, it runs a function called `process_message`. This function does four critical things:

### Step 1: The Idempotency Check (No Double-Charging)
```python
redis_idem_key = f"idempotent_txn:{payload['idempotency_key']}"
if redis_client.exists(redis_idem_key):
    return # Already processed!
```
What if a user's internet lags, so they angrily click the "Buy" button 5 times in one second? RabbitMQ will give us 5 identical order tickets. 
To prevent charging the user 5 times, we check a unique "Receipt ID" (idempotency key) in Redis. If we've seen it before, we throw the ticket in the trash.

### Step 2: The Atomic Wallet Check (Non-Blocking)
```python
deduct_sql = text("""
    UPDATE wallets SET balance = balance - :cost 
    WHERE user_id = :uid AND balance >= :cost 
    RETURNING balance
""")
result = db.execute(deduct_sql, {"cost": total_cost, "uid": user_id}).fetchone()
```
The worker needs to ask PostgreSQL: *"Does this user have enough money?"* 
In the past, we read the balance first, and updated it later. That caused a **Race Condition** if the user spammed the buy button. Now, we use a single Atomic SQL command to subtract the money *only if* they have enough. If it returns nothing, they don't have the funds!

### Step 3: The Atomic Lock (The Magic Line)
```python
new_stock = redis_client.decrby(inventory_key, quantity)
```
**This is the most important line of code in the application.**
We subtract the item from inventory using `DECRBY` (Decrement By). 

Because Redis is **Atomic**, it forces all 10 concurrent orders into a single-file line for exactly one microsecond. 
If there is 1 item left, and 2 workers run `DECRBY 1` at the exact same time:
*   Worker A gets `0`. It says: "Great, you got the last one!"
*   Worker B gets `-1`. It says: "Oops, sold out!" and instantly refunds the Redis inventory (`INCRBY`) AND refunds the PostgreSQL Wallet we deducted in Step 2!

### Step 4: The Final Save (The Saga Pattern)
Once the fast math is done, we save the final `Order` receipt.
But what if the PostgreSQL database crashes exactly right now? The Redis inventory would be decremented, but no order would be saved!
To prevent **Orphaned Inventory**, we wrap this in a `try/except` block (The Distributed Saga Pattern). If `db.commit()` fails, the except block instantly refunds the Redis inventory, refunds the database, and tells RabbitMQ not to delete the ticket so we can retry it later.

---

## Deep Technical Trade-offs

1. **Multi-Processing vs. Threads:** We chose `multiprocessing` to bypass the Python GIL. The trade-off is **RAM Usage**. A new process is an exact clone of the entire Python environment. Spawning 20 threads uses almost no RAM, but spawning 20 processes will quickly consume gigabytes of memory.
2. **High Prefetch vs. Low Prefetch:** We set our prefetch to 5. The advantage is throughput. The trade-off is **Risk of Trapped Messages**. If a worker grabs 5 tickets and suddenly crashes (e.g., runs out of memory), those 5 tickets are stuck until RabbitMQ realizes the connection died and returns them to the queue. A prefetch of 1 is safer, but much slower.
3. **`asyncio.to_thread` vs. Async Drivers:** We use `asyncio.to_thread` to push blocking database calls to a background thread. The trade-off is **Context-Switching Overhead**. Your CPU has to pause the main loop, spin up a thread, and switch contexts. The absolute best-case scenario would be using a fully asynchronous PostgreSQL driver (like `asyncpg`), but that requires rewriting the entire SQLAlchemy setup!
4. **Saga Pattern vs Dead-Letter Queues:** Our `try/except` Saga pattern is robust, but it introduces a new flaw: what if Redis itself crashes exactly when we try to run the `except` block's refund? The refund fails, and the script hard-crashes. In a true enterprise system, you would catch this total failure and route the ticket to a "Dead Letter Queue" (DLQ)—a special RabbitMQ bin where broken tickets wait for a human engineer to manually investigate and fix the database.

---

## Summary

`worker.py` is an advanced, high-performance background script. 

By combining **Multi-Processing** (to bypass Python's speed limits), **RabbitMQ Prefetch** (to grab tasks in bulk), **Async Threads** (to avoid waiting on the database), and **Redis Atomic Locks** (to prevent overselling), you have built a worker pool capable of handling Amazon-level flash sales!
