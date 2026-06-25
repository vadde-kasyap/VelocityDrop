from pydantic import BaseModel

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
