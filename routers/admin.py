from fastapi import APIRouter, HTTPException
import random
from database import SessionLocal, Product, Wallet
from schemas import DepositRequest, NewProductRequest
from cache import search_trie, redis_client

router = APIRouter()

# ---------------------------------------------------------
# Wallet Endpoints (Pre-Sale Loading)
# ---------------------------------------------------------
@router.post("/wallet/deposit")
async def deposit_funds(request: DepositRequest):
    """
    Simulates a user depositing money via Stripe/Bank before the flash sale.
    """
    if request.amount <= 0:
        return {"error": "Deposit amount must be greater than zero."}

    db = SessionLocal()
    
    wallet = db.query(Wallet).filter(Wallet.user_id == request.user_id).first()
    
    if wallet:
        wallet.balance += request.amount
    else:
        wallet = Wallet(user_id=request.user_id, balance=request.amount)
        db.add(wallet)
        
    db.commit()
    db.refresh(wallet)
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
@router.post("/admin/product")
async def add_new_product(product: NewProductRequest):
    """Adds a new product to the Database, Trie, and Redis simultaneously."""
    db = SessionLocal()
    product_name_clean = product.name.lower()
    
    existing = db.query(Product).filter(Product.name == product_name_clean).first()
    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="Product already exists. Use PUT /admin/product/{name} to update stock.")
        
    new_prod = Product(name=product_name_clean, stock=product.stock, price=product.price)
    db.add(new_prod)
    db.commit()
    db.close()
    
    search_trie.insert(product_name_clean)
    redis_client.set(f"inventory:{product_name_clean}", product.stock)
    
    for i in range(1, len(product_name_clean) + 1):
        redis_client.delete(f"search:{product_name_clean[:i]}")
    
    return {"status": "success", "message": f"Successfully added '{product.name}'."}

@router.put("/admin/product/{product_name}")
async def update_inventory(product_name: str, new_stock: int):
    """Updates stock in the Database and immediately syncs it to Redis."""
    db = SessionLocal()
    product_name_clean = product_name.lower()
    
    product = db.query(Product).filter(Product.name == product_name_clean).first()
    if not product:
        db.close()
        raise HTTPException(status_code=404, detail="Product not found.")
        
    product.stock = new_stock
    db.commit()
    db.close()
    
    redis_client.set(f"inventory:{product_name_clean}", new_stock)
    return {"status": "success", "message": f"Updated '{product_name_clean}' stock to {new_stock}."}

@router.post("/admin/seed-wallets")
async def mass_seed_wallets(num_users: int = 2000, min_amount: float = 500.0, max_amount: float = 5000.0):
    """
    Instantly generates thousands of users with randomized pre-loaded wallets.
    Crucial for simulating a realistic massive Locust flash sale.
    """
    db = SessionLocal()
    
    existing_count = db.query(Wallet).count()
    new_wallets = []
    
    for i in range(num_users):
        user_id = f"user_{existing_count + i + 1}"
        random_balance = round(random.uniform(min_amount, max_amount), 2)
        new_wallets.append(Wallet(user_id=user_id, balance=random_balance))
        
    db.bulk_save_objects(new_wallets)
    db.commit()
    db.close()
    
    return {
        "status": "success", 
        "message": f"Generated {num_users} new users with random balances between ₹{min_amount} and ₹{max_amount}."
    }
