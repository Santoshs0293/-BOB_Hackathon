import redis
from .config import settings
import json

redis_client = redis.from_url(settings.REDIS_URL)

def save_feature(key: str, feature: dict):
    redis_client.set(key, json.dumps(feature))

def load_feature(key: str):
    data = redis_client.get(key)
    return json.loads(data) if data else None
