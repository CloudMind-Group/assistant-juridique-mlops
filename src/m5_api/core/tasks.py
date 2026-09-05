import time
from celery import Celery

celery_app = Celery(
    "m5_tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)

@celery_app.task
def analyze_document_task(document_name: str):
    time.sleep(10)  # simule un traitement long (10 secondes)
    return {
        "document": document_name,
        "status": "completed",
        "summary": f"Analyse terminée pour '{document_name}' : 42 clauses détectées, 3 alertes de conformité.",
    }