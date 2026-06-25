import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import aio_pika
from aio_pika import connect_robust
from aio_pika.pool import Pool
from database import engine, Base, init_db, SessionLocal, Product
from cache import redis_client
from routers import search, checkout, admin

# 1. Automate Database Initialization
Base.metadata.create_all(bind=engine)

# 2. Initialize app
app = FastAPI(title="VelocityDrop API Gateway")

# 3. Add Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Include Routers
app.include_router(search.router)
app.include_router(checkout.router)
app.include_router(admin.router)

# --- RabbitMQ Pool Factory Functions ---
async def get_connection():
    return await connect_robust("amqp://guest:guest@localhost/")

async def get_channel():
    # Grabs a channel from the robust connection we set in app.state
    return await app.state.mq_connection.channel()


@app.on_event("startup")
async def startup_event():
    # 1. Trigger DB creation
    init_db()
    
    # 2. Read Products from PostgreSQL
    db = SessionLocal()
    products = db.query(Product).all()
    
    # 3. Build Redis Search Set and Inventory from DB data
    for p in products:
        # ZADD adds the product name to a Sorted Set with a score of 0
        redis_client.zadd("search_autocomplete", {p.name.lower(): 0})
        redis_client.set(f"inventory:{p.name.lower()}", p.stock)
        
    db.close()
    print(" Redis search index and inventory seeded directly from PostgreSQL!")
    
    # 4. Connect to RabbitMQ using Connection and Channel Pools
    try:
        loop = asyncio.get_running_loop()
        
        # Open a single robust connection
        app.state.mq_connection = await get_connection()
        
        # Create a pool of 20 channels. This multiplexes high-concurrency traffic!
        app.state.mq_channel_pool = Pool(get_channel, max_size=20, loop=loop)
        
        # Declare the queue once at startup using a channel from the pool
        async with app.state.mq_channel_pool.acquire() as channel:
            await channel.declare_queue("checkout_queue", durable=True)
            
        print(" Connected to RabbitMQ Channel Pool successfully.")
    except Exception as e:
        print(f" Failed to connect to RabbitMQ: {e}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)