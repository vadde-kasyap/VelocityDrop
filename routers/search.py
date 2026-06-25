from fastapi import APIRouter, Query
import json
from cache import redis_client, search_trie

router = APIRouter()

@router.get("/search")
async def autocomplete(q: str = Query(..., min_length=1)):
    prefix = q.lower()
    redis_key = f"search:{prefix}"

    cached_results = redis_client.get(redis_key)
    if cached_results:
        return {"source": "redis_cache", "results": json.loads(cached_results)}
    
    results = search_trie.search_prefix(prefix)
    if results:
        redis_client.set(redis_key, json.dumps(results), ex=60)
    return {"source": "trie_computation", "results": results}
