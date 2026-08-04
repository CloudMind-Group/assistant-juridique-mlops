import os
from pathlib import Path

def create_project_structure():
    # Liste dyal ga3 les dossiers li ghadi n7tajo f Module 1
    folders = [
        "data/raw",          # Les PDFs w Word bruts (kifma jbnahom)
        "data/interim",      # Textes extraits (après ingestion)
        "data/processed",    # Textes nettoyés w chunks (wajdin l RAG)
        "src/data",          # Scripts Python dyal data
        "dags"               # Dossier dyal Apache Airflow li ghat7tajih f lkher
    ]

    print("🚀 Création de l'arborescence dyal Module 1...")

    for folder in folders:
        # Créer le dossier
        Path(folder).mkdir(parents=True, exist_ok=True)
        print(f"📁 Dossier créé : {folder}")
        
        # Astuce Pro: Créer un fichier .gitkeep bach Git y39el 3la dossier khawi
        gitkeep_path = Path(folder) / ".gitkeep"
        if not gitkeep_path.exists():
            gitkeep_path.touch()

    print("✅ Arborescence m9adda 100% !")

if __name__ == "__main__":
    create_project_structure()