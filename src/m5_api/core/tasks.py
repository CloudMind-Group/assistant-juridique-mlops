import time
import os
from celery import Celery

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
celery_app = Celery(
    "m5_tasks",
    broker=f"redis://{REDIS_HOST}:6379/0",
    backend=f"redis://{REDIS_HOST}:6379/0",
)
@celery_app.task
def analyze_document_task(document_name: str):
    time.sleep(10)  # simule un traitement long (10 secondes)
    return {
        "document": document_name,
        "status": "completed",
        "summary": f"Analyse terminée pour '{document_name}' : 42 clauses détectées, 3 alertes de conformité.",
    }
