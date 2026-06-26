# A Beginner's Guide to `cache.py` (The Speed Engine)

If `main.py` is the front door of our application, `cache.py` is the **rocket engine** that makes everything insanely fast.

When you type "mac" into the search bar of an e-commerce store, you expect results to appear instantly before you even finish typing the word "book". If our app had to dig through PostgreSQL to search for "mac" every time a user pressed a key on their keyboard, the database would melt down.

To solve this, we decoupled our high-speed tools into `cache.py`. This file contains two things: a **Redis connection** and a **Trie data structure**. 

Let's break them down so that a first-year computer science student can completely understand what is happening under the hood!

---

## 1. The Redis Connection

At the very top of the file, you will see this line:
```python
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
```

**What is Redis?** 
Normally, a database (like PostgreSQL) saves data onto a hard drive. Hard drives are safe and permanent, but they are physically slow to read and write from. Redis is an **In-Memory Database**. It stores data entirely in your computer's RAM. Reading from RAM takes a fraction of a millisecond. 

We initialize this `redis_client` here so that the rest of our application (like `search.py` and `worker.py`) can import it and use it for two critical jobs:
1.  **Caching Search Results:** If 1,000 people search for "iphone", Redis saves the results the first time and hands it back instantly to the next 999 people without doing any math.
2.  **Inventory Locking:** Redis handles the atomic math (`DECRBY`) that mathematically guarantees we never oversell inventory during a flash sale. 

---

## 2. The Autocomplete Engine (Stateless Redis)

Before our latest architectural upgrade, we used a custom Python "Trie" to handle autocomplete. The fatal flaw with that approach was that it lived inside Python's local RAM. If we had 3 FastAPI servers, they all had different Tries. They would drift out of sync!

To fix this, we made our API **100% Stateless**. We moved the autocomplete engine directly into Redis using a feature called a **Sorted Set**.

### How `ZADD` Works (Adding a Product)
When an admin adds a "macbook" to the store, we run:
```python
redis_client.zadd("search_autocomplete", {"macbook": 0})
```
This drops "macbook" into a massive list in Redis, all with a score of `0`. Because the score is identical, Redis automatically sorts them alphabetically (Lexicographically). 

### How `ZRANGEBYLEX` Works (Finding Products)
When a user types "mac" in the search bar, the code does not scan a list of 100,000 products. Instead, we run:
```python
results = redis_client.zrangebylex("search_autocomplete", "[mac", "[mac\xff")
```
Redis instantly jumps to the section of the alphabetical list that starts with "mac", and grabs everything up to `\xff` (the maximum possible byte, effectively acting as a wildcard). 

Because Redis is so optimized, this search happens in $O(\log N)$ time. **It is lightning fast, and centrally shared by all workers!**

---

## Deep Technical Trade-offs

1. **Stateless APIs vs Stateful APIs:** We moved our Autocomplete engine out of Python memory and entirely into Redis. The trade-off is **Network Latency**. Reading a Python dictionary locally is technically faster than asking Redis over a network. However, the incredible advantage is that our API is now **Stateless**. We can run 50 servers behind a load balancer and they will never drift out of sync.
2. **Redis vs. Native Database Search:** We use Redis to cache our search results and inventory. The trade-off is **Distributed State Synchronization**. If an admin updates PostgreSQL manually using a SQL terminal, Redis won't know about it until someone writes a synchronization script. Native database features like PostgreSQL `LIKE` or `tsvector` are slower, but they are always 100% accurate.
3. **Memory Eviction (The RAM Limit):** Because Redis stores everything in memory, what happens if we add 100 million products and Redis runs out of RAM? Unlike PostgreSQL, which just buys more hard drives, Redis will crash or start deleting old data (depending on its `maxmemory-policy` configuration like LRU - Least Recently Used). The trade-off of absolute speed is an absolute hardware ceiling.

---
