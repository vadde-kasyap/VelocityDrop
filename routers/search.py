from fastapi import APIRouter, Query
from cache import redis_client

router = APIRouter()

@router.get("/search")
async def autocomplete(q: str = Query(..., min_length=1)):
    prefix = q.lower()
    
    # Stateless Redis Autocomplete using ZRANGEBYLEX
    # We query the Sorted Set for all strings lexicographically starting with the prefix
    # \xff is the maximum byte value, effectively acting as a wildcard.
    results = redis_client.zrangebylex("search_autocomplete", f"[{prefix}", f"[{prefix}\xff")
    
    return {"source": "redis_zrangebylex", "results": results}
