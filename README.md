# VelocityDrop ⚡

**High-Concurrency Flash Sale & Distributed Checkout Engine**

VelocityDrop is an event-driven e-commerce backend built to survive massive traffic spikes during flash sales. It is engineered to guarantee zero inventory overdraws under heavy load while delivering ultra-low latency product discovery.

## 🚀 The Architecture

To handle high concurrency without database locking or system crashes, this project decouples the traditional checkout flow using asynchronous messaging and in-memory data structures.

*   **Instant Discovery:** A custom **Redis Trie** data structure provides sub-50ms autocomplete search recommendations.
*   **Traffic Absorption:** **RabbitMQ** message queues ingest massive, sudden spikes in checkout requests, acting as a shock absorber for the database.
*   **Concurrency Control:** **Atomic Redis decrements** lock inventory in-memory instantly, completely eliminating race conditions and overselling.
*   **Data Integrity:** **PostgreSQL** serves as the final source of truth, securely recording ACID-compliant transaction states.

## 🛠️ Tech Stack

*   **Backend Engine:** Python, FastAPI
*   **Message Broker:** RabbitMQ
*   **In-Memory Cache & Search:** Redis
*   **Relational Database:** PostgreSQL
*   **Frontend UI:** Next.js, React

## 📈 Performance & Load Testing (Work in Progress)

*Benchmarking is currently being conducted using [Locust / K6] to simulate concurrent flash-sale traffic. Metrics will be updated upon test completion.*

*   **Target Search Latency:** < 50ms
*   **Target Throughput:** [Placeholder] requests/sec
*   **Error Rate Guarantee:** 0% inventory overdraws

## ⚙️ Local Setup & Installation

### Prerequisites
*   Docker & Docker Compose
*   Python 3.10+
*   Node.js (for Next.js frontend)

### 1. Clone the Repository
\`\`\`bash
git clone https://github.com/kasyapmittu/velocity-drop.git
cd velocity-drop
\`\`\`

### 2. Start Infrastructure (RabbitMQ, Redis, PostgreSQL)
\`\`\`bash
docker-compose up -d
\`\`\`

### 3. Run the FastAPI Backend
\`\`\`bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
uvicorn main:app --reload
\`\`\`

### 4. Run the Next.js Frontend
\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`
