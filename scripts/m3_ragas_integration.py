"""M1 -> M2 -> M3 evaluation integration."""

import mlflow

from src.m2_rag.corpus import load_m1_corpus
from src.m2_rag.factory import build_light_service
from src.m2_rag.models import RAGRequest

from src.m3_tracking.config import MLflowConfig
from src.m3_tracking.mlflow_tracker import MLflowTrackingHook
from src.m3_tracking.ragas_evaluator import RAGASEvaluationSample
from src.m3_tracking.evaluation_runner import EvaluationRunner


TRACKING_URI = "http://127.0.0.1:5000"
EXPERIMENT_NAME = "assistant-juridique-m3"


def local_dev_evaluator(records):
    """
    DEV evaluator only.

    This verifies the M3 evaluation pipeline.
    It is NOT an official RAGAS benchmark.
    """
    record = records[0]

    contexts = record["retrieved_contexts"]
    response = record["response"]

    context_available = 1.0 if contexts else 0.0
    answer_available = 1.0 if str(response).strip() else 0.0

    return {
        "dev_context_available": context_available,
        "dev_answer_available": answer_available,
        "dev_context_count": float(len(contexts)),
    }


def main():
    documents = load_m1_corpus()
    service = build_light_service(documents)

    config = MLflowConfig(
        tracking_uri=TRACKING_URI,
        experiment_name=EXPERIMENT_NAME,
        registered_model_name="assistant-juridique-rag",
    )

    tracker = MLflowTrackingHook(config)

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    request = RAGRequest(
        question="Quelle règle de droit est décrite dans le corpus ?",
        top_k=8,
    )

    with mlflow.start_run(run_name="m2-m3-evaluation-dev") as run:
        service.tracking_hook = tracker

        response = service.query(request)

        sample = RAGASEvaluationSample(
            question=request.question,
            answer=response.answer,
            contexts=[
                chunk.text
                for chunk in response.retrieved_chunks
            ],
        )

        runner = EvaluationRunner(
            tracker=tracker,
            evaluator=local_dev_evaluator,
        )

        evaluation = runner.run([sample])

        tracker.log_parameters(
            {
                "evaluation_type": "DEV_TEST",
                "corpus_documents": len(documents),
                "ground_truth_available": False,
            }
        )

        print("RUN_ID:", run.info.run_id)
        print("refused:", response.refused)
        print("citations:", len(response.citations))
        print("retrieved_chunks:", len(response.retrieved_chunks))
        print("evaluation:", evaluation.metrics)


if __name__ == "__main__":
    main()
