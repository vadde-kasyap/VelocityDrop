# A Beginner's Guide to `database.py` (The Permanent Vault)

In our architecture, Redis (`cache.py`) is used for lightning-fast math, and RabbitMQ is used for the waiting line. But what happens if the server crashes and loses power? Everything in RAM is wiped out. 

That is why we need a **Permanent Vault**. In VelocityDrop, that vault is PostgreSQL, and `database.py` is the map that tells our Python code how to talk to it.

Let's break down exactly how this file works for a beginner!

---

## 1. What is an ORM?

If you want to talk to a SQL database, you normally have to write raw SQL strings, like this:
```sql
SELECT * FROM products WHERE name = 'macbook m4';
```
Writing SQL strings inside Python is messy and prone to errors. Instead, we use a tool called **SQLAlchemy**. 

SQLAlchemy is an **ORM** (Object-Relational Mapper). It acts as an automatic translator. It lets us write normal, clean Python classes, and it translates those classes into SQL commands for us behind the scenes.

---

## 2. The Engine and the "Sweet Spot"

At the top of the file, you will see the connection settings:

```python
DATABASE_URL = "postgresql://admin:adminpassword@127.0.0.1:5432/velocity_db"

engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

1.  **The URL:** This tells Python exactly where PostgreSQL lives (IP address `127.0.0.1`), what port it listens on (`5432`), and the password to get in.
2.  **The Engine (Connection Pool):** Remember in the architecture guide where we talked about "Connection Exhaustion"? If 1,000 users try to connect to PostgreSQL at the same time, it will crash. By setting `pool_size=20`, SQLAlchemy creates a strict "pool" of 20 connections. If a 21st user tries to connect, SQLAlchemy makes them wait in line until one of the 20 connections is free. This is the **Sweet Spot** that keeps the database perfectly safe from crashing.
3.  **The Session:** Think of a Session as a "ticket". Whenever a file in our app (like `worker.py` or `admin.py`) wants to read or write data, it creates a new Session, uses it, and then closes it.

---

## 3. The Database Tables (Python Classes)

Next, we define our tables. Because we are using SQLAlchemy, we don't write `CREATE TABLE`. We just write Python classes that inherit from `Base`!

### The Product Table
```python
class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    stock = Column(Integer, default=0)
    price = Column(Float, default=0.0)
```
This stores the official inventory. Notice the `index=True` on the `name` column. An "index" is like the index at the back of a textbook—it makes searching for a product by name incredibly fast for the database.

### The Wallet Table
```python
class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)
    balance = Column(Float, default=0.0)
```
This stores the user's money. When a user deposits funds (via `admin.py`) or buys an item (via `worker.py`), we use this table to check if they have enough cash, and then we deduct it.

### The Order Table
```python
class Order(Base):
    __tablename__ = "orders"
    ...
    status = Column(String) # "pending", "success", "failed_sold_out", "failed_funds"
```
This is the permanent history of every checkout attempt. Even if an order fails because the user didn't have enough money, we save a record of it here.

---

## 4. The Initialization Step

At the very bottom of the file, we have this function:
```python
def init_db():
    Base.metadata.create_all(bind=engine)
```
When `main.py` starts up, it calls this function. SQLAlchemy looks at the `Product`, `Wallet`, and `Order` classes we wrote, figures out exactly what the SQL should look like, and automatically creates the tables in PostgreSQL if they don't already exist.

This means you never have to manually log into PostgreSQL to set up your tables. The Python code does it for you!

---

## Deep Technical Trade-offs

1. **ORM vs. Raw SQL:** We use SQLAlchemy (an ORM) to interact with PostgreSQL. The enormous advantage is that it completely protects us from SQL Injection attacks and makes the code clean. The trade-off is **Performance Overhead**. SQLAlchemy adds CPU overhead translating Python to SQL. If you need to insert 100,000 rows instantly, traditional ORM methods are too slow. (This is why in `admin.py`, we had to bypass standard `db.add()` and use the highly optimized `db.bulk_save_objects()` trick to seed 2,000 wallets instantly!).
2. **Strict Connection Pooling vs. Unrestricted Scaling:** We strictly set `pool_size=20`. The advantage is that the database is mathematically protected from Connection Exhaustion crashes. The trade-off is **Application Bottlenecking**. If we accidentally spawn 50 workers, 30 of them will completely freeze waiting for an available database connection. A strict pool protects the DB, but pushes the failure back onto the Python application.
3. **ACID Properties vs Speed:** PostgreSQL is an "ACID-compliant" database (Atomicity, Consistency, Isolation, Durability). This means when an order is saved, it is mathematically guaranteed to be permanently written to the physical hard drive. The trade-off for this absolute safety is that PostgreSQL is fundamentally slower than Redis or RabbitMQ, which is exactly why we use it only as the final "permanent vault" at the very end of the checkout process.

---

## Summary

`database.py` is the blueprint for our permanent storage. 
It sets up a strict connection pool so we never crash the database under heavy load, and it uses SQLAlchemy to map simple Python classes directly into PostgreSQL tables. 

Whenever the rest of the application needs to save something forever, it grabs a `SessionLocal` from this file!
