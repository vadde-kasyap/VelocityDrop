from locust import HttpUser, task, between
import random
import uuid

class FlashSaleUser(HttpUser):
    # Reduced wait time to hit the server faster
    wait_time = between(0.5, 1.5)
    
    # 1. Define your catalog of available products here
    # ⚠️ Make sure every product listed here has been added to your database!
    target_products = [
        "mac book m4"
        
    ]
    target_quantity=[1,2,3]

    @task
    def click_buy_button(self):
        # 2. Randomly select one product for this specific user's cart
        selected_product = random.choice(self.target_products)
        quantity_dynamic=random.choice(self.target_quantity)
        
        # Only use the seeded users (user_1 to user_2000)
        payload = {
            "user_id": f"user_{random.randint(1, 2000)}",
            "product_name": selected_product, 
            "quantity": quantity_dynamic
        }
        
        headers = {
            "Idempotency-Key": str(uuid.uuid4())
        }

        self.client.post("/checkout", json=payload, headers=headers)