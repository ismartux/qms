from django.core.cache import cache
from typing import Dict, List, Any


def fetch_bitable_rows(*, template_id: int) -> List[Dict[str, Any]]:
    """
    READ-ONLY snapshot fetch.
    NO outbound calls.
    """
    cache_key = f"dynamic_forms:bitable_rows:{template_id}"
    return cache.get(cache_key, [])