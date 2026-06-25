from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import aio_pika

from database import engine, Base, init_db, SessionLocal, Product
from cache import search_trie, redis_client
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

@app.on_event("startup")
async def startup_event():
    # 1. Trigger DB creation
    init_db()
    
    # 2. Read Products from PostgreSQL
    db = SessionLocal()
    products = db.query(Product).all()
    
    # 3. Build Trie and Redis from DB data
    for p in products:
        search_trie.insert(p.name.lower())
        redis_client.set(f"inventory:{p.name.lower()}", p.stock)
        
    db.close()
    print("✅ Trie built and Redis inventory seeded directly from PostgreSQL!")
    
    # 4. Connect to RabbitMQ
    try:
        connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
        channel = await connection.channel()
        queue = await channel.declare_queue("checkout_queue", durable=True)
        app.state.rabbitmq_channel = channel
        print("✅ Connected to RabbitMQ successfully.")
    except Exception as e:
        print(f"❌ Failed to connect to RabbitMQ: {e}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)