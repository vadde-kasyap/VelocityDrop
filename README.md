# VelocityDrop

**High-concurrency flash-sale and distributed checkout engine.**

VelocityDrop is an event-driven e-commerce backend built to handle sudden flash-sale traffic spikes without ever overselling inventory. It combines a FastAPI API gateway, a stateless Redis Lexicographical Search (Sorted Sets) for instant autocomplete, a RabbitMQ checkout queue, a distributed Saga-pattern worker pool, PostgreSQL for persistence, and a Next.js storefront + admin dashboard.

---

## Architecture

```
Browser (Next.js)
      │
      ▼
FastAPI Gateway  ──► Redis (Stateless Lexicographical search + atomic inventory counters)
      │
      ▼
RabbitMQ Queue
      │
      ▼
Worker Process  ──► PostgreSQL (products, wallets, orders)
```

| Component | Role |
|---|---|
| **FastAPI** | Accepts search, checkout, wallet, and admin requests |
| **Redis Search** | Stateless Lexicographical Search (`ZRANGEBYLEX`) for autocomplete |
| **Redis Inventory Counter** | Atomic `DECRBY` prevents overselling under concurrency |
| **RabbitMQ** | Decouples HTTP requests from database writes; absorbs traffic spikes |
| **Worker Pool** | Multi-process pool consuming queue messages, validating funds, and finalizing orders |
| **PostgreSQL** | Source of truth for products, wallets, and order history |
| **Next.js** | Storefront (`/`) and admin dashboard (`/admin`) |

---

## Tech Stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn, Pydantic, SQLAlchemy
- **Cache / Locks:** Redis
- **Queue:** RabbitMQ
- **Database:** PostgreSQL
- **Frontend:** Next.js 16, React
- **Load testing:** Locust
- **Local infra:** Docker Compose

---

## Repository Layout

```
VelocityDrop/
├── main.py                  # FastAPI entry point & startup events
├── cache.py                 # Redis connection setup
├── schemas.py               # Pydantic data models for API requests
├── database.py              # SQLAlchemy models & DB init
├── worker.py                # Multi-process RabbitMQ checkout consumer
├── routers/                 # Modular API endpoints
│   ├── search.py            # GET /search
│   ├── checkout.py          # POST /checkout
│   └── admin.py             # Admin and wallet routes
├── locustfile.py            # Locust flash-sale load test
├── docker-compose.yml       # Redis + RabbitMQ + PostgreSQL
├── requirements.txt         # Python dependencies
└── velocity-frontend/       # Next.js frontend
    └── src/app/
        ├── page.js          # Storefront (search + checkout)
        └── admin/page.js    # Admin dashboard
```

---

## Prerequisites

Make sure you have the following installed before starting:

| Tool | Version | Download |
|---|---|---|
| Docker Desktop | Latest | https://www.docker.com/products/docker-desktop |
| Python | 3.10+ | https://www.python.org/downloads |
| Node.js | 18+ | https://nodejs.org |

---

## Local Setup — Step by Step

### Step 1 — Clone the repository

```bash
git clone https://github.com/vadde-kasyap/VelocityDrop.git
cd VelocityDrop
```

---

### Step 2 — Start infrastructure with Docker

This starts Redis, RabbitMQ, and PostgreSQL in the background.

```bash
docker-compose up -d
```

Verify all three containers are running:

```bash
docker ps
```

You should see `velocity_postgres`, `velocity_redis`, and `velocity_rabbitmq` all with status `Up`.

| Service | URL |
|---|---|
| Redis | `localhost:6379` |
| RabbitMQ AMQP | `localhost:5672` |
| RabbitMQ Dashboard | http://localhost:15672 — login: `guest` / `guest` |
| PostgreSQL | `localhost:5432` — db: `velocity_db`, user: `admin` |

---

### Step 3 — Set up the Python environment

```bash
python -m venv venv
```

Activate the virtual environment:

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

Install all dependencies:

```bash
pip install -r requirements.txt
```

---

### Step 4 — Run the FastAPI backend

From the project root (with the venv active):

```bash
uvicorn main:app --reload
```

| URL | Description |
|---|---|
| http://127.0.0.1:8000 | API base |
| http://127.0.0.1:8000/docs | Swagger interactive docs |

The first startup automatically creates all database tables in PostgreSQL.

---

### Step 5 — Run the checkout worker pool

Open a **second terminal**, activate the same venv, and run:

```bash
# Windows (forces UTF-8 for Rs symbol and emoji)
$env:PYTHONUTF8=1; python worker.py --workers 2 --prefetch 5
```

By default, this spawns a **Multi-Process Worker Pool** tuned for a stable "Sweet Spot": 2 isolated processes, each handling up to 5 concurrent orders via RabbitMQ prefetch. This allows the system to comfortably process **10 concurrent orders** simultaneously without overwhelming local database connections or CPU.

The workers listen on the `checkout_queue` RabbitMQ queue, process orders asynchronously, deduct wallet balances, and write results to PostgreSQL.

---

### Step 6 — Run the frontend

Open a **third terminal**:

```bash
cd velocity-frontend
npm install
npm run dev
```

| URL | Description |
|---|---|
| http://localhost:3000 | Storefront (search + checkout) |
| http://localhost:3000/admin | Admin dashboard |

> **WSL2 / VM users:** If you access the frontend from a non-localhost address (e.g. `172.x.x.x`), the `allowedDevOrigins` setting in `velocity-frontend/next.config.mjs` already includes the common WSL2 adapter IP. If your IP differs, add it there.

---

### Step 7 — Seed data (required before testing)

You must add at least one product and seed wallets before checkout will work.
<img width="1364" height="635" alt="image" src="https://github.com/user-attachments/assets/558e1f55-d726-46d6-a059-b1c00e5e482e" />

**Option A — Use the Admin Dashboard UI:**
1. Go to http://localhost:3000/admin
2. **Add Product** — enter a name, stock quantity, and price → click Save
3. **Seed Data** — enter `2000` users → click Generate

**Option B — Use the API directly:**

```bash
# Add a product
curl -X POST http://127.0.0.1:8000/admin/product \
  -H "Content-Type: application/json" \
  -d '{"name": "mac book m4", "stock": 500, "price": 1299.99}'

# Seed 2000 user wallets with $500–$5000 each
curl -X POST "http://127.0.0.1:8000/admin/seed-wallets?num_users=2000&min_amount=500&max_amount=5000"
```

---

## Load Testing with Locust

### Configure the product target

Open [`locustfile.py`](locustfile.py) and set `target_products` to match a product you added in Step 7:

```python
target_products = [
    "mac book m4"   # must already exist in the database
]
```

### Run Locust

**Windows (PowerShell — uses the venv directly):**
```powershell
.\venv\Scripts\locust.exe -f locustfile.py --host=http://127.0.0.1:8000
```

**macOS / Linux (with venv activated):**
```bash
locust -f locustfile.py --host=http://127.0.0.1:8000
```

Open the Locust Web UI at **http://localhost:8089** and enter:

| Setting | Recommended |
|---|---|
| Number of users | `500` |
| Ramp up (users/sec) | `50` |
| Host | `http://127.0.0.1:8000` |

Click **Start Swarming**.

### What to watch

- **Locust dashboard** — Real-time RPS, latency, and failure rate
- <img width="1364" height="635" alt="image" src="https://github.com/user-attachments/assets/77054f82-0ecb-4689-b6fb-950390a29ea3" />

- **RabbitMQ dashboard** (http://localhost:15672 → Queues tab) — Watch the queue spike and drain as the worker processes orders
- <img width="1364" height="635" alt="image" src="https://github.com/user-attachments/assets/d7e3c8c8-8dd9-4dd9-85b2-07830880c99b" />

- **Worker terminal** — See each `✅ SUCCESS` or `❌ FAILED` order log in real time

---

## Scaling to High Concurrency

The system is designed to handle thousands of concurrent users seamlessly:

1. **Multi-Process Worker Pool**: By running `python worker.py --workers 2`, the system spawns 2 isolated processes, bypassing Python's GIL while keeping hardware usage light.
2. **RabbitMQ Prefetch**: The `--prefetch 5` flag tells each worker to ask RabbitMQ for 5 unacknowledged messages at once.
3. **Non-blocking DB Calls**: Blocking SQLAlchemy database operations are offloaded to thread pools (`asyncio.to_thread()`), ensuring the main event loop is never blocked while waiting for PostgreSQL.
4. **Connection Pool Safety**: Tuned to a "Sweet Spot" (2 workers × 5 prefetch = **10 concurrent orders**), ensuring default PostgreSQL connection limits are respected without deadlocks, while still draining a 1000-user queue in ~3 seconds.

---

## API Reference

### `GET /search?q={prefix}`
Returns autocomplete suggestions from the in-memory Trie (Redis-cached for 60 s).

### `POST /checkout`
Queues a checkout request via RabbitMQ. Returns `202 Accepted` immediately.
```json
{ "user_id": "user_1", "product_name": "mac book m4", "quantity": 1 }
```
Include an `Idempotency-Key` header to prevent duplicate orders.

### `POST /wallet/deposit`
Credits a user's wallet.
```json
{ "user_id": "user_1", "amount": 1000 }
```

### `POST /admin/product`
Adds a new product to Postgres, Trie, and Redis simultaneously.
```json
{ "name": "iphone 16", "stock": 200, "price": 999.99 }
```

### `PUT /admin/product/{name}?new_stock={n}`
Updates stock in Postgres and Redis.

### `POST /admin/seed-wallets?num_users=2000&min_amount=500&max_amount=5000`
Bulk-generates test user wallets for load testing.

---

## How It Prevents Overselling

1. A checkout request arrives and is immediately queued — no DB write yet.
2. The worker dequeues it and runs an **idempotency check** in Redis. Duplicate requests are silently dropped.
3. The worker **validates the user's wallet balance** against the product price.
4. Only if funds are sufficient does it call `DECRBY` on the Redis inventory counter — an **atomic operation** that handles thousands of concurrent calls without race conditions.
5. If the counter goes negative (stock exhausted), the worker **rolls back** the decrement and records a `failed_sold_out` order.
6. On success, the wallet is debited and a `success` order is written to PostgreSQL.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `locust` not found | Use `.\venv\Scripts\locust.exe` (Windows) or activate venv first |
| `docker-compose` not found | Make sure Docker Desktop is running and you're inside the `VelocityDrop/` folder |
| Search returns no results | Add at least one product via `/admin/product` first |
| Checkout fails with "not found" | Ensure the product name in `locustfile.py` exactly matches what you added (it's stored lowercase) |
| Frontend shows wrong data | Hard-refresh the browser (Ctrl+Shift+R) to clear any stale Next.js cache |
| RabbitMQ connection error | Wait ~10 s after `docker-compose up` for RabbitMQ to finish initializing, then restart uvicorn |

---

## License

MIT
