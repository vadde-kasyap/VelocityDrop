# A Beginner's Guide to the `routers` Folder

In our previous guides, we learned that `main.py` is just "Grand Central Station." It sets up the tracks, but it doesn't actually process any trains. 

The **`routers/` folder** is where the actual trains run! This is where the business logic of our API endpoints lives. By separating our code into three different files (`search.py`, `checkout.py`, and `admin.py`), developers can easily find and fix code without scrolling through thousands of lines.

At the top of every file in this folder, you will see:
```python
router = APIRouter()
```
An `APIRouter` is essentially a "mini" FastAPI app. We build the endpoints on this mini-app, and then `main.py` simply "plugs it in" using `app.include_router()`.

Let's look at the three files inside this folder!

---

## 1. `search.py` (The Search Engine)

This file contains exactly one endpoint: `GET /search`. It is responsible for making the frontend search bar feel instantly responsive.

When a user types "mac", this file does a highly optimized query:

1.  **Check the Redis Sorted Set (`ZRANGEBYLEX`):**
    ```python
    results = redis_client.zrangebylex("search_autocomplete", f"[{prefix}", f"[{prefix}\xff")
    ```
    It asks Redis to jump to the `search_autocomplete` alphabetical list, find everything starting with "mac", and return it instantly. This entirely replaces the old stateful Python Trie and makes the API 100% stateless!

---

## 2. `checkout.py` (The Flash Sale Drop)

This file contains the most critical endpoint in our app: `POST /checkout`. 

When a user clicks "Buy", we absolutely **cannot** talk to PostgreSQL, or the database will crash from too much traffic. Instead, this endpoint does three very fast things:

1.  **Creates a Receipt (Idempotency Key):**
    ```python
    if not idempotency_key:
        idempotency_key = str(uuid.uuid4())
    ```
    If the frontend didn't give us a unique receipt ID, we generate one. This prevents the user from being double-charged if they double-click the buy button.

2.  **Packages the Ticket:**
    It takes the user's ID, the product, and the quantity, and packs them into a JSON payload.

3.  **Acquires a Channel from the Pool and Publishes:**
    ```python
    async with request.app.state.mq_channel_pool.acquire() as channel:
        await channel.default_exchange.publish(
            message, routing_key="checkout_queue"
        )
    ```
    This is the key architectural upgrade. Instead of grabbing a single shared channel that would serialize all traffic, it calls `mq_channel_pool.acquire()`. This borrows one of the **20 pre-opened channels** from the pool created in `main.py`. The message is published, and the channel is immediately returned to the pool for someone else to use. If all 20 channels are busy, the `acquire()` call politely waits until one becomes free—no crashes, no dropped messages.
    Finally, it returns a `202 Accepted` response. It does zero math. It just drops the ticket and walks away!

---

## 3. `admin.py` (The Manager's Office)

Unlike `search.py` and `checkout.py` (which are built for insane speed), `admin.py` is for the store managers. These endpoints don't get hit by 10,000 users at once, so it is perfectly safe for them to talk directly to the PostgreSQL database.

It contains four endpoints:

*   **`POST /wallet/deposit`**: Simply finds a user's wallet in PostgreSQL and adds money to it.
*   **`POST /admin/product`**: Adds a new product to the PostgreSQL database. **Crucially**, it also injects the new product into the Redis Sorted Set. If it didn't do this, users wouldn't be able to search for or buy the new product until the server restarted!
*   **`PUT /admin/product/{product_name}`**: Allows an admin to restock an item. It updates the database and instantly overwrites the `inventory:product` counter in Redis so the flash sale can continue.
*   **`POST /admin/seed-wallets`**: A load-testing cheat code. It instantly generates 2,000 fake users with random amounts of money in their wallets using a highly optimized database bulk-insert. We use this to set up our Locust load tests!

---

## Deep Technical Trade-offs

1. **Fire-and-Forget vs. Awaiting Responses:** In `checkout.py`, we throw a JSON string into RabbitMQ and immediately return `202 Accepted`. The trade-off is **Error Handling**. If the user doesn't have enough money, they won't find out until the background worker processes the ticket later. We traded instantaneous error-checking for the ability to survive a million users clicking "Buy" at the same time.
2. **`async def` + Channel Pool vs. Old `def` + Single Channel:** The original checkout endpoint was a synchronous `def` function using a single shared channel. Under flash-sale load this was a double bottleneck: the thread pool had limited slots, and the single channel serialized all publishes. The new endpoint is fully `async def` and uses `mq_channel_pool.acquire()` to borrow from a pool of 20 channels. The trade-off is that the code is more complex to reason about (async context managers, pool lifecycle), but the gain is that the endpoint can handle thousands of concurrent checkout requests without blocking or queuing inside the application layer.
3. **Queue Backpressure:** Throwing messages into RabbitMQ is incredibly fast, but RabbitMQ has a physical limit based on its server's RAM and disk space. If users submit orders faster than our workers can process them, RabbitMQ will eventually fill up. If we don't configure "Backpressure" (telling FastAPI to stop accepting requests when RabbitMQ is 90% full), RabbitMQ will crash, taking down the entire flash sale.
4. **Double-Writing (Admin) vs. Cache Invalidation:** In `admin.py`, when a new product is added, we write it to PostgreSQL, and then we manually insert it into Redis. The trade-off is **Code Fragility**. If PostgreSQL succeeds but Redis crashes exactly one millisecond later, our database and cache are permanently out of sync. A more robust (but far more complex) trade-off would be using a tool like Debezium to read PostgreSQL logs and automatically update Redis in the background.

---

## Summary

By looking at the `routers/` folder, you can clearly see the **Separation of Concerns**:
*   `search.py` only talks to the Caches.
*   `checkout.py` only talks to the Queue.
*   `admin.py` talks to the Database to manage state.

If a new developer joins the team and is asked to "fix a bug in the deposit system," they don't have to read 500 lines of search and checkout code. They know exactly where to go: `routers/admin.py`. That is the power of a modular architecture!
