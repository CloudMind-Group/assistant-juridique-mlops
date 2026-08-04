import os
import requests
import fitz  # PyMuPDF pour les PDFs
import docx  # python-docx pour les Word
import json
from pathlib import Path

# --- Configuration des dossiers ---
RAW_DIR = Path("data/raw")
INTERIM_DIR = Path("data/interim")
RAW_DIR.mkdir(parents=True, exist_ok=True)
INTERIM_DIR.mkdir(parents=True, exist_ok=True)

class LegalDataIngestor:
    def __init__(self):
        self.documents = []

    # 1. Connecteur pour Portails Officiels (ex: API Légifrance, Adala)
    def ingest_from_url(self, url, source_name):
        print(f"🌍 Téléchargement depuis : {source_name}...")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            self.documents.append({
                "source": source_name,
                "type": "url/html",
                "content": response.text
            })
            print(f"✅ Succès : {source_name}")
        except Exception as e:
            print(f"❌ Erreur URL {source_name} : {e}")

    # 2. Connecteur pour Dépôts PDF Internes
    def ingest_from_pdf(self, filepath):
        print(f"📄 Lecture du PDF : {filepath.name}...")
        try:
            doc = fitz.open(filepath)
            text = ""
            for page in doc:
                text += page.get_text("text") + "\n"
            
            self.documents.append({
                "source": filepath.name,
                "type": "pdf",
                "content": text
            })
            print(f"✅ Succès : {filepath.name}")
        except Exception as e:
            print(f"❌ Erreur PDF {filepath.name} : {e}")

    # 3. Connecteur pour Dépôts DOCX Internes
    def ingest_from_docx(self, filepath):
        print(f"📝 Lecture du Word : {filepath.name}...")
        try:
            doc = docx.Document(filepath)
            text = "\n".join([para.text for para in doc.paragraphs])
            
            self.documents.append({
                "source": filepath.name,
                "type": "docx",
                "content": text
            })
            print(f"✅ Succès : {filepath.name}")
        except Exception as e:
            print(f"❌ Erreur DOCX {filepath.name} : {e}")

    # Sauvegarde des données ingérées
    def save_data(self, output_filename="ingested_data.json"):
        output_path = INTERIM_DIR / output_filename
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=4)
        print(f"\n💾 Toutes les données sont sauvegardées dans : {output_path}")


if __name__ == "__main__":
    ingestor = LegalDataIngestor()

    # TEST : 1. Ingestion depuis un lien web (Exemple: page loi public)
    # Hna kaddir les urls li ghatjibi mnhom data
    ingestor.ingest_from_url("https://httpbin.org/html", "Loi_Test_API")

    # TEST : 2 & 3. Parcourir le dossier data/raw pour les PDFs et DOCX
    for file_path in RAW_DIR.iterdir():
        if file_path.suffix.lower() == '.pdf':
            ingestor.ingest_from_pdf(file_path)
        elif file_path.suffix.lower() == '.docx':
            ingestor.ingest_from_docx(file_path)

    # Sauvegarder le résultat unifié
    ingestor.save_data()