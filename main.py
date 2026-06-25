from fastapi import FastAPI, Query, Header, HTTPException
from pydantic import BaseModel
import uvicorn
import redis
import json
import aio_pika
import uuid
import random

# IMPORT YOUR NEW DATABASE FILE HERE
from database import init_db, SessionLocal, Product, Wallet
from fastapi import FastAPI, Query, Header
from fastapi.middleware.cors import CORSMiddleware # 1. Make sure this import is present

import random  # or any other top-level imports
from fastapi import FastAPI, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from database import engine, Base


# 1. Automate Database Initialization
# This line tells SQLAlchemy to build the tables the moment the app starts
Base.metadata.create_all(bind=engine)
# 1. Initialize app FIRST
app = FastAPI(title="VelocityDrop API Gateway")

# 2. Add Middleware SECOND (Before ANY @app.get or @app.post lines!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Wildcard temporarily opens the gates for debugging
    allow_credentials=False,  # Note: Must be False if allow_origins is "*"
    allow_methods=["*"],
    allow_headers=["*"],
)




redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

class OrderRequest(BaseModel):
    user_id: str
    product_name: str
    quantity: int = 1
class DepositRequest(BaseModel):
    user_id: str
    amount: float
class NewProductRequest(BaseModel):
    name: str
    stock: int
    price: float
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False

class Trie:
    def __init__(self):
        self.root = TrieNode()
    def insert(self, word):
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True
    def search_prefix(self, prefix):
        node = self.root
        for char in prefix:
            if char not in node.children:
                return []
            node = node.children[char]
        return self.collections_all_words(node, prefix)
    def collections_all_words(self, node, current_prefix):
        results = []
        if node.is_end_of_word:
            results.append(current_prefix)
        for char, child_node in node.children.items():
            results.extend(self.collections_all_words(child_node, current_prefix + char))        
        return results

search_trie = Trie()

@app.on_event("startup")
async def startup_event():
    # 1. TRIGGER THE DATABASE CREATION HERE
    init_db()
    
    # 2. READ PRODUCTS FROM POSTGRESQL
    db = SessionLocal()
    products = db.query(Product).all()
    
    # 3. BUILD TRIE AND REDIS FROM DATABASE DATA
    for p in products:
        # BUG FIX: always lowercase so prefix search matches lowercased queries
        search_trie.insert(p.name.lower())
        redis_client.set(f"inventory:{p.name.lower()}", p.stock)
        
    db.close()
    print("✅ Trie built and Redis inventory seeded directly from PostgreSQL!")
    
    # 4. CONNECT TO RABBITMQ
    try:
        connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
        channel = await connection.channel()
        queue = await channel.declare_queue("checkout_queue", durable=True)
        app.state.rabbitmq_channel = channel
        print("✅ Connected to RabbitMQ successfully.")
    except Exception as e:
        print(f"❌ Failed to connect to RabbitMQ: {e}")

@app.get("/search")
async def autocomplete(q: str = Query(..., min_length=1)):
    prefix = q.lower()
    redis_key = f"search:{prefix}"

    cached_results = redis_client.get(redis_key)
    if cached_results:
        return {"source": "redis_cache", "results": json.loads(cached_results)}
    
    results = search_trie.search_prefix(prefix)
    if results:
        redis_client.set(redis_key, json.dumps(results), ex=60)
    return {"source": "trie_computation", "results": results}

@app.post("/checkout", status_code=202)
async def process_checkout(order: OrderRequest, idempotency_key: str = Header(None)):
    if not idempotency_key:
        idempotency_key = str(uuid.uuid4())

    payload = {
        "idempotency_key": idempotency_key,
        "user_id": order.user_id,
        "product_name": order.product_name,
        "quantity": order.quantity,
        "status": "pending"
    }

    channel = app.state.rabbitmq_channel
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
# ---------------------------------------------------------
# Wallet Endpoints (Pre-Sale Loading)
# ---------------------------------------------------------
@app.post("/wallet/deposit")
async def deposit_funds(request: DepositRequest):
    """
    Simulates a user depositing money via Stripe/Bank before the flash sale.
    """
    if request.amount <= 0:
        return {"error": "Deposit amount must be greater than zero."}

    db = SessionLocal()
    
    # 1. Look up the user's wallet
    wallet = db.query(Wallet).filter(Wallet.user_id == request.user_id).first()
    
    # 2. Add the money (or create a new wallet if they don't have one)
    if wallet:
        wallet.balance += request.amount
    else:
        wallet = Wallet(user_id=request.user_id, balance=request.amount)
        db.add(wallet)
        
    db.commit()
    db.refresh(wallet) # Get the updated data from the database
    current_balance = wallet.balance
    db.close()
    
    return {
        "status": "success",
        "message": f"Successfully deposited ₹{request.amount}",
        "user_id": request.user_id,
        "new_balance": current_balance
    }

# ---------------------------------------------------------
# Admin & Load Testing Endpoints
# ---------------------------------------------------------
@app.post("/admin/product")
async def add_new_product(product: NewProductRequest):
    """Adds a new product to the Database, Trie, and Redis simultaneously."""
    db = SessionLocal()
    product_name_clean = product.name.lower()
    
    # 1. Ensure it doesn't already exist
    existing = db.query(Product).filter(Product.name == product_name_clean).first()
    if existing:
        db.close()
        # BUG FIX: raise HTTP 400 so the frontend can correctly detect this as an error
        raise HTTPException(status_code=400, detail="Product already exists. Use PUT /admin/product/{name} to update stock.")
        
    # 2. Save to Source of Truth (Postgres)
    new_prod = Product(name=product_name_clean, stock=product.stock, price=product.price)
    db.add(new_prod)
    db.commit()
    db.close()
    
    # 3. Inject into High-Speed Caches (Trie & Redis)
    search_trie.insert(product_name_clean)
    redis_client.set(f"inventory:{product_name_clean}", product.stock)
    
    # BUG FIX: Invalidate any stale Redis search-cache entries for every prefix of this
    # product's name so the next search hits the Trie and returns fresh results immediately.
    for i in range(1, len(product_name_clean) + 1):
        redis_client.delete(f"search:{product_name_clean[:i]}")
    
    return {"status": "success", "message": f"Successfully added '{product.name}'."}

@app.put("/admin/product/{product_name}")
async def update_inventory(product_name: str, new_stock: int):
    """Updates stock in the Database and immediately syncs it to Redis."""
    db = SessionLocal()
    product_name_clean = product_name.lower()
    
    product = db.query(Product).filter(Product.name == product_name_clean).first()
    if not product:
        db.close()
        # BUG FIX: raise HTTP 404 so the frontend can correctly detect this as an error
        raise HTTPException(status_code=404, detail="Product not found.")
        
    # Update Postgres
    product.stock = new_stock
    db.commit()
    db.close()
    
    # Update Redis
    redis_client.set(f"inventory:{product_name_clean}", new_stock)
    return {"status": "success", "message": f"Updated '{product_name_clean}' stock to {new_stock}."}

@app.post("/admin/seed-wallets")
async def mass_seed_wallets(num_users: int = 2000, min_amount: float = 500.0, max_amount: float = 5000.0):
    """
    Instantly generates thousands of users with randomized pre-loaded wallets.
    Crucial for simulating a realistic massive Locust flash sale.
    """
    db = SessionLocal()
    
    # Check how many users already exist so we don't crash on duplicate user_ids
    existing_count = db.query(Wallet).count()
    
    new_wallets = []
    
    for i in range(num_users):
        # We add 1 so the IDs start at user_1 instead of user_0, matching your Locust script
        user_id = f"user_{existing_count + i + 1}"
        
        # Generate a random balance between 500 and 5000, rounded to 2 decimal places
        random_balance = round(random.uniform(min_amount, max_amount), 2)
        
        new_wallets.append(Wallet(user_id=user_id, balance=random_balance))
        
    # bulk_save_objects is a highly optimized SQLAlchemy method for inserting thousands of rows instantly
    db.bulk_save_objects(new_wallets)
    db.commit()
    db.close()
    
    return {
        "status": "success", 
        "message": f"Generated {num_users} new users with random balances between ₹{min_amount} and ₹{max_amount}."
    }
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)