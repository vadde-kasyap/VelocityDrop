from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

# Connects to the Postgres container running in Docker
DATABASE_URL = "postgresql://admin:adminpassword@127.0.0.1:5432/velocity_db"

# Connection pooling tuned for high concurrency (up to 30 concurrent DB connections per process)
engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ---------------------------------------------------------
# 1. Database Table Schemas
# ---------------------------------------------------------
class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    stock = Column(Integer, default=0)
    price = Column(Float, default=0.0) # NEW: Added price for the wallet deduction

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    product_name = Column(String)
    quantity = Column(Integer)
    status = Column(String) # "pending", "success", "failed_sold_out", "failed_funds"

class Wallet(Base): # NEW: The Digital Wallet Table
    __tablename__ = "wallets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True) # Each user gets exactly 1 wallet
    balance = Column(Float, default=0.0)

# ---------------------------------------------------------
# 2. Database Initialization & Seeding
# ---------------------------------------------------------
def init_db():
    """
    Creates the tables in Postgres and seeds the starting inventory.
    """
    Base.metadata.create_all(bind=engine)
    

        
