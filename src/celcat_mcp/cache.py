from datetime import timedelta
from cachetools import TTLCache


calendar_cache: TTLCache = TTLCache(maxsize=256, ttl=timedelta(minutes=10).total_seconds())
resource_cache: TTLCache = TTLCache(maxsize=128, ttl=timedelta(hours=1).total_seconds())
room_list_cache: TTLCache = TTLCache(maxsize=16, ttl=timedelta(hours=6).total_seconds())
