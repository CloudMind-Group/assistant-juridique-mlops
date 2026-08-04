import os
import fitz  # PyMuPDF li installeyna f l'étape 1
import pytesseract
from PIL import Image
import io
import json
from pathlib import Path

# ⚠️ HNA KANGOLO L PYTHON FIN KAYN TESSERACT F PC DYALEK
# Ila installitih f blassa khra, bddli had l chemin
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

RAW_DIR = Path("data/raw")
INTERIM_DIR = Path("data/interim")

def correct_legal_text(text):
    """
    Hadi hiya la 'correction orthographique juridique' li talbin 3andek f la tâche.
    Tesseract kayghlet f chi 7rof mli kayscanni, hna kants77ohom.
    """
    corrections = {
        "artide": "article",
        "Ioi": "loi",
        "tribunaI": "tribunal",
        "droits": "droits"
    }
    for wrong, right in corrections.items():
        text = text.replace(wrong, right)
        text = text.replace(wrong.capitalize(), right.capitalize())
    return text

def ocr_scanned_pdf(pdf_path):
    print(f"🔍 Démarrage de l'OCR pour : {pdf_path.name}")
    doc = fitz.open(pdf_path)
    full_text = ""
    
    # Kandozo 3la ga3 les pages dyal l PDF
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        
        # Kan7wlo la page l tsawira (PixMap) b résolution mzyana
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        # Kan3tiw tsawira l Tesseract bach yjbed lkatba (b français w anglais)
        text = pytesseract.image_to_string(img, lang='fra+eng')
        full_text += text + "\n"
        print(f"   ✔️ Page {page_num + 1} traitée.")
        
    # Kandirow l correction 9bel ma n-retourniw l texte
    return correct_legal_text(full_text)

if __name__ == "__main__":
    print("🚀 Lancement du Pipeline OCR...")
    ocr_results = []
    
    # N9elbo 3la les PDFs w ndirou lihom OCR
    for file_path in RAW_DIR.iterdir():
        if file_path.suffix.lower() == '.pdf':
            text = ocr_scanned_pdf(file_path)
            ocr_results.append({
                "source": file_path.name,
                "type": "pdf_ocr",
                "content": text
            })
            
    # Nsauvegardiw nateeja f interim
    output_path = INTERIM_DIR / "ocr_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ocr_results, f, ensure_ascii=False, indent=4)
        
    print(f"✅ OCR Salâ! L'output rah f {output_path}")