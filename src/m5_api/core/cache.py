import json
import hashlib
import logging
import os
import redis

logger = logging.getLogger(__name__)

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")

# Délais bornés : sans eux, un Redis injoignable ou figé fait attendre la
# requête indéfiniment. Un cache qui ralentit le service qu'il accélère est
# pire que pas de cache du tout.
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=6379,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)

CACHE_EXPIRATION_SECONDS = 3600  # 1 heure

# Le cache est une optimisation, pas un garde-fou : son indisponibilité ne doit
# pas empêcher de répondre. Avant ce repli, un Redis éteint faisait remonter
# une `ConnectionError` depuis `get_cached_response` jusqu'au client, et
# `POST /chat` renvoyait 500 alors que la chaîne RAG, elle, fonctionnait.
#
# L'incident est signalé une fois par état plutôt qu'à chaque requête : une
# ligne par appel noierait le journal, aucune ligne masquerait la panne.
_cache_indisponible = False


def _signaler_indisponible(exc: redis.RedisError) -> None:
    global _cache_indisponible
    if not _cache_indisponible:
        logger.warning(
            "Cache Redis indisponible (%s) — les réponses sont servies sans "
            "cache. Démarrer le service `redis` de docker-compose.yml pour le "
            "rétablir.",
            type(exc).__name__,
        )
        _cache_indisponible = True


def _signaler_retabli() -> None:
    global _cache_indisponible
    if _cache_indisponible:
        logger.info("Cache Redis de nouveau joignable.")
        _cache_indisponible = False


def make_cache_key(question: str) -> str:
    normalized = question.strip().lower()
    return "chat:" + hashlib.sha256(normalized.encode()).hexdigest()


def get_cached_response(question: str):
    key = make_cache_key(question)
    try:
        cached = redis_client.get(key)
    except redis.RedisError as exc:
        _signaler_indisponible(exc)
        return None
    _signaler_retabli()
    if cached:
        return json.loads(cached)
    return None


def set_cached_response(question: str, response_data: dict):
    key = make_cache_key(question)
    try:
        redis_client.set(key, json.dumps(response_data), ex=CACHE_EXPIRATION_SECONDS)
    except redis.RedisError as exc:
        _signaler_indisponible(exc)
