# VelocityDrop

**High-concurrency flash-sale and distributed checkout engine.**

VelocityDrop is an event-driven e-commerce system built to handle sudden flash-sale traffic without overselling inventory. It combines a FastAPI API gateway, Redis-backed search and inventory locks, RabbitMQ queueing, PostgreSQL persistence, and a Next.js frontend.

## Architecture

VelocityDrop separates the customer-facing request path from the final order-processing path:

- **FastAPI API gateway** accepts search, checkout, wallet, and admin requests.
- **Redis Trie search cache** provides fast product autocomplete and short-lived cached search results.
- **RabbitMQ checkout queue** absorbs traffic spikes and lets checkout requests return quickly.
- **Worker process** consumes checkout jobs, applies idempotency checks, validates wallets, and finalizes orders.
- **Redis atomic inventory counters** prevent concurrent purchases from overdrawing stock.
- **PostgreSQL** stores products, wallets, and completed or failed order records.
- **Next.js frontend** provides the user-facing interface.

## Tech Stack

- **Backend:** Python, FastAPI, Pydantic, Uvicorn
- **Worker:** Python, aio-pika
- **Cache and locks:** Redis
- **Queue:** RabbitMQ
- **Database:** PostgreSQL, SQLAlchemy
- **Frontend:** Next.js, React
- **Load testing:** Locust
- **Local infrastructure:** Docker Compose

## Repository Layout

```text
velocityDrop/
|-- main.py                 # FastAPI API gateway
|-- worker.py               # RabbitMQ checkout worker
|-- database.py             # SQLAlchemy models and database initialization
|-- docker-compose.yml      # Redis, RabbitMQ, and PostgreSQL
|-- locustfile.py           # Load-test scenarios
|-- velocity-frontend/      # Next.js frontend
|-- .gitignore
|-- LICENSE
`-- README.md
```

## Local Setup

### Prerequisites

- Docker and Docker Compose
- Python 3.10+
- Node.js 20+ recommended

### 1. Clone the Repository

```bash
git clone https://github.com/vadde-kasyap/VelocityDrop
cd velocity-drop
```

If you are working from the current local folder, the project root is the `velocityDrop` directory.

### 2. Start Redis, RabbitMQ, and PostgreSQL

```bash
docker-compose up -d
```

Services started by Compose:

- Redis: `localhost:6379`
- RabbitMQ: `localhost:5672`
- RabbitMQ dashboard: `http://localhost:15672` with `guest` / `guest`
- PostgreSQL: `localhost:5432`
- PostgreSQL database: `velocity_db`

### 3. Create a Python Environment

```bash
python -m venv venv
```

On Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

On macOS/Linux:

```bash
source venv/bin/activate
```

Install backend dependencies:

```bash
pip install fastapi uvicorn redis aio-pika sqlalchemy psycopg2-binary pydantic locust
```

### 4. Run the FastAPI Backend

From the project root, start the server with hot-reloading enabled:

\`\`\`bash
uvicorn main:app --reload
\`\`\`

The API runs at:

- API: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

### 5. Run the Checkout Worker

Open a second terminal from the project root and activate the same Python environment.

```bash
python worker.py
```

The worker consumes messages from the `checkout_queue` RabbitMQ queue and writes final order outcomes to PostgreSQL.

### 6. Run the Frontend

Open another terminal:

```bash
cd velocity-frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:3000`.

## API Overview

### Search Products

```http
GET /search?q=phone
```

Returns autocomplete results from Redis cache when available, otherwise from the in-memory Trie.

### Submit Checkout

```http
POST /checkout
Idempotency-Key: unique-request-id
Content-Type: application/json

{
  "user_id": "user_1",
  "product_name": "iphone",
  "quantity": 1
}
```

Returns `202 Accepted` after queueing the checkout request.

### Deposit Wallet Funds

```http
POST /wallet/deposit
Content-Type: application/json

{
  "user_id": "user_1",
  "amount": 1000
}
```

### Add Product

```http
POST /admin/product
Content-Type: application/json

{
  "name": "iphone",
  "stock": 100,
  "price": 799
}
```

### Update Inventory

```http
PUT /admin/product/iphone?new_stock=250
```

### Seed Test Wallets

```http
POST /admin/seed-wallets?num_users=2000&min_amount=500&max_amount=5000
```

## Load Testing

After the backend, worker, and Docker services are running:

```bash
locust -f locustfile.py
```

Then open `http://localhost:8089` and target `http://127.0.0.1:8000`.

Current performance goals:

- Search latency target: under 50 ms
- Checkout path: asynchronous queue acceptance under burst traffic
- Inventory guarantee: no successful orders beyond available Redis-backed stock

### 7. Load Testing & Visualizing Queues (Locust + RabbitMQ)
To prove the system's resilience under flash-sale conditions, you can simulate massive traffic spikes and watch the event-driven architecture absorb the load in real-time.

**Step A: Open the RabbitMQ Management Dashboard**
* Navigate to: `http://localhost:15672`
* **Username:** `guest` | **Password:** `guest`
* *What to watch:* Click on the **Queues** tab. Keep this open. When the load test starts, you will see the message queue spike instantly to absorb the traffic, protecting the PostgreSQL database from bottlenecks.

**Step B: Start the Locust Load Tester**
Open a new terminal, ensure your virtual environment is activated, and start the Locust server:
\`\`\`bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
locust -f locustfile.py
\`\`\`

**Step C: Launch the Flash Sale Simulation**
* Navigate to the Locust Web UI: `http://localhost:8089`
* **Number of users:** Enter `1000` (Simulating 1,000 concurrent buyers)
* **Spawn rate:** Enter `100` (Users added per second)
* **Host:** `http://localhost:8000` (Your FastAPI backend)
* Click **Start swarming**.

**Step D: Observe the System**
* Watch the **Locust dashboard** to see the sub-50ms response times and the 0% failure rate.
* Switch back to the **RabbitMQ dashboard** to watch the message broker seamlessly queue and process the checkout payloads while the atomic Redis locks prevent inventory overdraws.
