# VelocityDrop

**High-concurrency flash-sale and distributed checkout engine.**

VelocityDrop is an event-driven e-commerce backend built to handle sudden flash-sale traffic spikes without ever overselling inventory. It combines a FastAPI API gateway, a stateless Redis Lexicographical Search (Sorted Sets) for instant autocomplete, a RabbitMQ checkout queue, a distributed Saga-pattern worker pool, PostgreSQL for persistence, and a Next.js storefront + admin dashboard.

---

## 🏗️ Architecture

<details>
<summary><b>👁️ Click to view Architecture Diagram</b></summary>
<br>

```mermaid
graph TD
    Client("💻 Browser (Next.js)") -->|HTTP Requests| API["🚀 FastAPI Gateway"]
    
    API -->|1. Autocomplete (ZRANGEBYLEX)<br>2. Inventory Lock (DECRBY)| Redis[("⚡ Redis<br>(Search & Locks)")]
    
    API -->|Fire & Forget| MQ[["📬 RabbitMQ Queue"]]
    
    MQ -->|Consume Tickets| Worker["👷 Worker Processes (Saga Pattern)"]
    
    Worker -->|Saga Rollback (INCRBY)| Redis
    Worker -->|Atomic UPDATE RETURNING| DB[("🗄️ PostgreSQL<br>(Products, Wallets, Orders)")]
```

</details>

<br>

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

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.10+, FastAPI, Uvicorn, Pydantic, SQLAlchemy |
| **Cache / Locks** | Redis |
| **Queue** | RabbitMQ |
| **Database** | PostgreSQL |
| **Frontend** | Next.js 16, React |
| **Load Testing** | Locust |
| **Local Infra** | Docker Compose |

---

## 📂 Repository Layout

```text
VelocityDrop/
├── 🚀 main.py                  # FastAPI entry point & startup events
├── ⚡ cache.py                 # Redis connection setup
├── 🛠️ schemas.py               # Pydantic data models for API requests
├── 🗃️ database.py              # SQLAlchemy models & DB init
├── 👷 worker.py                # Multi-process RabbitMQ checkout consumer
├── 📁 routers/                 # Modular API endpoints
│   ├── 🔍 search.py            # GET /search
│   ├── 🛒 checkout.py          # POST /checkout
│   └── 🔐 admin.py             # Admin and wallet routes
├── 🧪 locustfile.py            # Locust flash-sale load test
├── 🐳 docker-compose.yml       # Redis + RabbitMQ + PostgreSQL
├── 📦 requirements.txt         # Python dependencies
└── 🖥️ velocity-frontend/       # Next.js frontend
    └── 📁 src/app/
        ├── 🛍️ page.js          # Storefront (search + checkout)
        └── 📊 admin/page.js    # Admin dashboard
```

---

## ✅ Prerequisites

Make sure you have the following installed before starting:

| Tool | Version | Download |
|---|---|---|
| **Docker Desktop** | Latest | https://www.docker.com/products/docker-desktop |
| **Python** | 3.10+ | https://www.python.org/downloads |
| **Node.js** | 18+ | https://nodejs.org |

> **⚠️ Windows users:** Make sure Docker Desktop is running before proceeding. You can verify by running `docker --version` in a terminal.

---

## 🚀 Local Setup — Step by Step

### Step 1 — Clone the repository

> Works the same on Windows, macOS, and Linux.

```bash
git clone https://github.com/vadde-kasyap/VelocityDrop.git
cd VelocityDrop
```

---

### Step 2 — Start infrastructure with Docker

This starts Redis, RabbitMQ, and PostgreSQL in the background. Works the same on all platforms.

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

> **⏱️ Note:** Wait about 10 seconds after `docker-compose up -d` before starting the API, to give RabbitMQ time to fully initialize.

---

### Step 3 — Set up the Python virtual environment

**Create the virtual environment** (same on all platforms):

```bash
python -m venv venv
```

**Activate it:**

<details>
<summary><b>🪟 Windows (PowerShell)</b></summary>

```powershell
.\venv\Scripts\Activate.ps1
```

> If you get an execution policy error, first run:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

</details>

<details>
<summary><b>🍎 macOS / Linux (Terminal)</b></summary>

```bash
source venv/bin/activate
```

</details>

<br>

After activation, your prompt will show `(venv)`. Then install all dependencies:

```bash
pip install -r requirements.txt
```

---

### Step 4 — Run the FastAPI backend

> Make sure your `(venv)` is active.

<details>
<summary><b>🪟 Windows (PowerShell)</b></summary>

```powershell
$env:PYTHONUTF8=1; .\venv\Scripts\uvicorn.exe main:app --reload
```

</details>

<details>
<summary><b>🍎 macOS / Linux (Terminal)</b></summary>

```bash
uvicorn main:app --reload
```

</details>

<br>

| URL | Description |
|---|---|
| http://127.0.0.1:8000 | API base |
| http://127.0.0.1:8000/docs | Swagger interactive docs (try all endpoints here!) |

> **✅ First startup:** The server automatically creates all database tables in PostgreSQL on first boot.

---

### Step 5 — Run the checkout worker pool

Open a **second terminal**, activate the same `venv`, and run the worker:

<details>
<summary><b>🪟 Windows (PowerShell)</b></summary>

```powershell
.\venv\Scripts\Activate.ps1
$env:PYTHONUTF8=1; python worker.py --workers 2 --prefetch 5
```

</details>

<details>
<summary><b>🍎 macOS / Linux (Terminal)</b></summary>

```bash
source venv/bin/activate
python worker.py --workers 2 --prefetch 5
```

</details>

<br>

| Flag | Default | Description |
|---|---|---|
| `--workers` | `2` | Number of parallel OS processes |
| `--prefetch` | `5` | Max unacknowledged RabbitMQ messages per worker |

> **🧠 Sweet Spot:** `2 workers × 5 prefetch = 10 concurrent orders` — enough to drain a 1,000-user queue in ~3 seconds without overwhelming local DB connections.

The workers will log every processed order in real time:
```
✅ SUCCESS: user_42 × 1 mac book m4 | Wallet: ₹1,234.56 | Stock left: 499
❌ INSUFFICIENT FUNDS: user_99 needs ₹1,299.99, has ₹200.00
```

---

### Step 6 — Run the frontend

Open a **third terminal**:

<details>
<summary><b>🪟 Windows (PowerShell)</b></summary>

```powershell
cd velocity-frontend
npm install
npm run dev
```

</details>

<details>
<summary><b>🍎 macOS / Linux (Terminal)</b></summary>

```bash
cd velocity-frontend
npm install
npm run dev
```

</details>

<br>

| URL | Description |
|---|---|
| http://localhost:3000 | Storefront (search + checkout) |
| http://localhost:3000/admin | Admin dashboard |

> **WSL2 / VM users:** If you access the frontend from a non-localhost address (e.g. `172.x.x.x`), the `allowedDevOrigins` setting in `velocity-frontend/next.config.mjs` already includes the common WSL2 adapter IP. If your IP differs, add it there.

---

### Step 7 — Seed data (required before testing)

You must add at least one product and seed wallets before checkout will work.

<img width="1364" height="635" alt="Admin Dashboard" src="https://github.com/user-attachments/assets/558e1f55-d726-46d6-a059-b1c00e5e482e" />

**Option A — Use the Admin Dashboard UI:**
1. Go to http://localhost:3000/admin
2. **Add Product** — enter a name, stock quantity, and price → click Save
3. **Seed Data** — enter `2000` users → click Generate

**Option B — Use the API directly (curl):**

<details>
<summary><b>🪟 Windows (PowerShell)</b></summary>

```powershell
# Add a product
Invoke-RestMethod -Uri "http://127.0.0.1:8000/admin/product" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"name": "mac book m4", "stock": 500, "price": 1299.99}'

# Seed 2000 user wallets
Invoke-RestMethod -Uri "http://127.0.0.1:8000/admin/seed-wallets?num_users=2000&min_amount=500&max_amount=5000" `
  -Method POST
```

</details>

<details>
<summary><b>🍎 macOS / Linux (Terminal)</b></summary>

```bash
# Add a product
curl -X POST http://127.0.0.1:8000/admin/product \
  -H "Content-Type: application/json" \
  -d '{"name": "mac book m4", "stock": 500, "price": 1299.99}'

# Seed 2000 user wallets
curl -X POST "http://127.0.0.1:8000/admin/seed-wallets?num_users=2000&min_amount=500&max_amount=5000"
```

</details>

---

## 🧪 Load Testing with Locust

### Step 1 — Configure the product target

Open [`locustfile.py`](locustfile.py) and set `target_products` to match a product you added:

```python
target_products = [
    "mac book m4"   # must already exist in the database
]
```

### Step 2 — Run Locust

<details>
<summary><b>🪟 Windows (PowerShell)</b></summary>

```powershell
.\venv\Scripts\locust.exe -f locustfile.py --host=http://127.0.0.1:8000
```

</details>

<details>
<summary><b>🍎 macOS / Linux (Terminal)</b></summary>

```bash
locust -f locustfile.py --host=http://127.0.0.1:8000
```

</details>

<br>

Open the Locust Web UI at **http://localhost:8089** and enter:

| Setting | Recommended |
|---|---|
| Number of users | `500` |
| Ramp up (users/sec) | `50` |
| Host | `http://127.0.0.1:8000` |

Click **Start Swarming**.

### What to watch

- **Locust dashboard** — Real-time RPS, latency, and failure rate
- <img width="1364" height="635" alt="Locust Dashboard" src="https://github.com/user-attachments/assets/77054f82-0ecb-4689-b6fb-950390a29ea3" />

- **RabbitMQ dashboard** (http://localhost:15672 → Queues tab) — Watch the queue spike and drain as the worker processes orders
- <img width="1364" height="635" alt="RabbitMQ Queue Spike" src="https://github.com/user-attachments/assets/7d50bddc-4c21-4117-b90a-62933f2ef971" />
- <img width="1364" height="635" alt="RabbitMQ Queue Drain" src="https://github.com/user-attachments/assets/7d3bf39a-ddba-43db-aa1b-b7c37fff2ae9" />

- **Worker terminal** — See each `✅ SUCCESS` or `❌ FAILED` order log in real time

---

## ⚡ Scaling to High Concurrency

The system is designed to handle thousands of concurrent users seamlessly:

1. **Multi-Process Worker Pool**: By running `python worker.py --workers 2`, the system spawns 2 isolated processes, bypassing Python's GIL while keeping hardware usage light.
2. **RabbitMQ Prefetch**: The `--prefetch 5` flag tells each worker to ask RabbitMQ for 5 unacknowledged messages at once.
3. **Non-blocking DB Calls**: Blocking SQLAlchemy database operations are offloaded to thread pools (`asyncio.to_thread()`), ensuring the main event loop is never blocked while waiting for PostgreSQL.
4. **Connection Pool Safety**: Tuned to a "Sweet Spot" (2 workers × 5 prefetch = **10 concurrent orders**), ensuring default PostgreSQL connection limits are respected without deadlocks, while still draining a 1000-user queue in ~3 seconds.
5. **RabbitMQ Channel Pooling**: The API Gateway uses `aio_pika.Pool` to multiplex thousands of concurrent checkout requests across 20 persistent RabbitMQ channels, preventing OS-level socket exhaustion and heartbeat timeouts during massive traffic spikes.

---

## 📖 API Reference

### `GET /search?q={prefix}`
Returns autocomplete suggestions instantly using the stateless Redis Lexicographical Search (`ZRANGEBYLEX`).

**Example response:**
```json
{ "source": "redis_zrangebylex", "results": ["mac book m4"] }
```

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
Adds a new product to Postgres and the Redis Lexicographical Set simultaneously.
```json
{ "name": "iphone 16", "stock": 200, "price": 999.99 }
```

### `PUT /admin/product/{name}?new_stock={n}`
Updates stock in Postgres and Redis.

### `POST /admin/seed-wallets?num_users=2000&min_amount=500&max_amount=5000`
Bulk-generates test user wallets for load testing.

---

## 🛡️ How It Prevents Overselling

1. A checkout request arrives and is immediately queued — no DB write yet.
2. The worker dequeues it and runs an **idempotency check** in Redis. Duplicate requests are silently dropped.
3. The worker executes an **atomic SQL command** (`UPDATE wallets ... WHERE balance >= cost RETURNING balance`) — the balance check and deduction happen in one uninterruptible database operation, making wallet race conditions mathematically impossible.
4. Only if funds are sufficient does it call `DECRBY` on the Redis inventory counter — an **atomic operation** that handles thousands of concurrent calls without race conditions.
5. If the counter goes negative (stock exhausted), the worker **rolls back** the decrement (`INCRBY`) and records a `failed_sold_out` order.
6. If the database commit fails at the very last second, the **Saga Pattern** kicks in — rolling back the Redis inventory *and* the wallet deduction, and requeuing the ticket so no order is ever lost.

---

## 🐛 Troubleshooting

| Problem | Fix |
|---|---|
| `locust` not found | **Windows:** Use `.\venv\Scripts\locust.exe`. **Mac/Linux:** Run `source venv/bin/activate` first |
| `uvicorn` not found | **Windows:** Use `.\venv\Scripts\uvicorn.exe`. **Mac/Linux:** Run `source venv/bin/activate` first |
| `docker-compose` not found | Make sure Docker Desktop is running and you're inside the `VelocityDrop/` folder |
| Unicode / emoji errors (Windows) | Set `$env:PYTHONUTF8=1` before running `python worker.py` |
| PowerShell Activate.ps1 blocked | Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` once |
| Search returns no results | Add at least one product via `/admin/product` first |
| Checkout fails with "not found" | Ensure the product name in `locustfile.py` exactly matches what you added (stored lowercase) |
| Frontend shows wrong data | Hard-refresh the browser (`Ctrl+Shift+R` on Windows, `Cmd+Shift+R` on Mac) |
| RabbitMQ connection error | Wait ~10 s after `docker-compose up` for RabbitMQ to finish initializing, then restart the API server |
| Worker shows negative wallet | This is expected — the Saga rollback catches it. Re-seed wallets with `/admin/seed-wallets` |

---

## 📄 License

MIT