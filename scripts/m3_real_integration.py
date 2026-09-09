"""Real local integration smoke: M1 corpus -> M2 RAG -> M3 MLflow."""

import mlflow

from src.m2_rag.corpus import load_m1_corpus
from src.m2_rag.factory import build_light_service
from src.m2_rag.models import RAGRequest
from src.m3_tracking.config import MLflowConfig
from src.m3_tracking.mlflow_tracker import MLflowTrackingHook


TRACKING_URI = "http://127.0.0.1:5000"
EXPERIMENT_NAME = "assistant-juridique-m3"


def main() -> None:
    # 1. Charger les vraies sorties M1
    documents = load_m1_corpus()

    print(f"M1 documents loaded: {len(documents)}")

    # 2. Construire le pipeline M2 light sur ce corpus
    service = build_light_service(documents)

    # 3. Configurer le tracker M3 vers le serveur MLflow local
    tracker = MLflowTrackingHook(
        MLflowConfig(
            tracking_uri=TRACKING_URI,
            experiment_name=EXPERIMENT_NAME,
            registered_model_name="assistant-juridique-rag",
        )
    )

    # build_light_service ne prend pas encore tracking_hook en argument,
    # donc on injecte le hook sur le RAGService retourné.
    service.tracking_hook = tracker

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    # 4. Une vraie requête M2 sur les documents M1
    request = RAGRequest(
        question="Quelle règle de droit est décrite dans le corpus ?",
        top_k=8,
    )

    # 5. Le run MLflow englobe l'exécution RAG
    with mlflow.start_run(run_name="m1-m2-m3-real-corpus") as run:
        tracker.log_parameters(
            {
                "module": "M3",
                "pipeline": "M1->M2->M3",
                "corpus_documents": len(documents),
                "retriever": "hybrid-bm25-dense",
                "execution_mode": "light",
            }
        )

        response = service.query(request)

        print("RUN_ID:", run.info.run_id)
        print("refused:", response.refused)
        print("refusal_reason:", response.refusal_reason)
        print("citations:", len(response.citations))
        print("retrieved_chunks:", len(response.retrieved_chunks))
        print("prompt_version:", response.prompt_version)
        print("model_version:", response.model_version)
        print("latencies:", response.latencies)

        if response.citations:
            print("first_citation_doc:", response.citations[0].doc_id)
            print("first_citation_chunk:", response.citations[0].chunk_id)


if __name__ == "__main__":
    main()
