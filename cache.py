import redis

# Decoded responses (strings instead of bytes) is crucial for ZRANGEBYLEX to work cleanly
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Note: The custom Python Trie has been fully removed.
# We now use Redis Sorted Sets (ZADD and ZRANGEBYLEX) to handle 
# search autocomplete in a 100% stateless and distributed manner!
