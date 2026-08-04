"""
Airflow DAG: legal_ingest_v2

Daily orchestration of the M1 pipeline:
    run_ingestion -> run_quality_check -> notify_m2_imane

- run_ingestion: extracts/cleans/validates data/raw/ into data/processed/
- run_quality_check: validates data/processed/ and writes quality_report.json
  (fails the task, blocking notify_m2_imane, if any document fails checks)
- notify_m2_imane: reads quality_report.json and signals M2 that a fresh,
  quality-checked corpus is ready to index (logs + a READY flag file that
  M2's own DAG/pipeline can poll for)

Owner: Douae (Module 1 — Data Pipeline & Ingestion).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# Repo root must be importable (for `python -m src.m1_ingestion...` and for
# the notify task, which imports the quality report path helpers directly).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logger = logging.getLogger("airflow.task.legal_ingest_v2")

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"
QUALITY_REPORT_PATH = REPO_ROOT / PROCESSED_DIR / "quality_report.json"
M2_READY_FLAG_PATH = REPO_ROOT / PROCESSED_DIR / "READY_FOR_M2.flag"

default_args = {
    "owner": "douae",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def _notify_m2_imane(**context) -> None:
    """Signal Module 2 (Imane) that a validated corpus is ready to index."""
    if not QUALITY_REPORT_PATH.exists():
        raise AirflowFailException(f"Quality report not found: {QUALITY_REPORT_PATH}")

    report = json.loads(QUALITY_REPORT_PATH.read_text(encoding="utf-8"))
    if report.get("failed", 1) > 0:
        raise AirflowFailException(
            f"{report.get('failed')} document(s) failed quality checks; "
            "not notifying M2. See quality_report.json for details."
        )

    payload = {
        "notified_at": datetime.utcnow().isoformat(),
        "dag_run_id": context.get("run_id"),
        "processed_dir": PROCESSED_DIR,
        "metadata_index": f"{PROCESSED_DIR}/metadata.jsonl",
        "total_documents": report.get("total_documents"),
        "pass_rate": report.get("pass_rate"),
    }
    M2_READY_FLAG_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(
        "M2 (Imane) notified: %d documents ready in %s (pass_rate=%.1f%%)",
        report.get("total_documents", 0),
        PROCESSED_DIR,
        report.get("pass_rate", 0.0) * 100,
    )


with DAG(
    dag_id="legal_ingest_v2",
    description="M1 — ingest, validate quality, and notify M2 (Imane) daily",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["m1", "ingestion", "legal-ai"],
) as dag:

    run_ingestion = BashOperator(
        task_id="run_ingestion",
        bash_command=(
            f"cd {REPO_ROOT} && "
            f"python -m src.m1_ingestion.ingest --raw-dir {RAW_DIR} --out-dir {PROCESSED_DIR}"
        ),
    )

    run_quality_check = BashOperator(
        task_id="run_quality_check",
        bash_command=(
            f"cd {REPO_ROOT} && "
            f"python -m src.m1_ingestion.quality --processed-dir {PROCESSED_DIR} --fail-on-error"
        ),
    )

    notify_m2_imane = PythonOperator(
        task_id="notify_m2_imane",
        python_callable=_notify_m2_imane,
    )

    run_ingestion >> run_quality_check >> notify_m2_imane
