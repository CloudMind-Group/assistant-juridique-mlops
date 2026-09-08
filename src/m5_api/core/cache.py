import json
import hashlib
import os
import redis

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

CACHE_EXPIRATION_SECONDS = 3600  # 1 heure

def make_cache_key(question: str) -> str:
    normalized = question.strip().lower()
    return "chat:" + hashlib.sha256(normalized.encode()).hexdigest()

def get_cached_response(question: str):
    key = make_cache_key(question)
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    return None

def set_cached_response(question: str, response_data: dict):
    key = make_cache_key(question)
    redis_client.set(key, json.dumps(response_data), ex=CACHE_EXPIRATION_SECONDS)
    