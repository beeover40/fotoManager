import os
import shutil
import base64
import json
import requests
from database import init_db, save_image  # Deine vorhandene Funktion

IMPORT_DIR = "01_Import"
DONE_BASE = "03_Done"

OLLAMA_URL = "http://localhost:11434/api/generate"

# Kategorien basierend auf Tags
TAG_CATEGORIES = {
    "startnummer": "Startnummer",
    "rot": "Roter_Anzug",
    "ski": "Ski",
    "helm": "Helm"
}

def extract_structured_data(response_text):
    """
    Versucht, strukturierte Daten aus der Antwort zu extrahieren.
    Falls kein JSON gefunden wird, wird eine Standardstruktur erstellt.
    """
    try:
        # Entferne mögliche Vor- oder Nachtexte
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        if start_idx != -1 and end_idx > start_idx:
            json_str = response_text[start_idx:end_idx]
            parsed = json.loads(json_str)
            return parsed
    except json.JSONDecodeError:
        pass

    # Fallback: Erstelle Standardstruktur
    return {
        "description": response_text,
        "numbers": [],
        "colors": [],
        "texts": []
    }

def ollama_analyze_image(image_path):
    # Strukturierter Prompt für gemma3
    prompt = """
    Analysiere dieses Bild detailliert und antworte NUR mit gültigem JSON im folgenden Format:
    {
      "description": "Eine kurze Beschreibung des Bildes",
      "numbers": ["Liste erkannter Zahlen/Nummern"],
      "colors": ["Liste dominanter Farben"],
      "texts": ["Liste sichtbarer Texte oder Schriftzüge"]
    }

    Konzentriere dich besonders auf:
    - Startnummern oder andere Zahlen
    - Farben der Kleidung oder Ausrüstung
    - Sichtbare Texte, Logos oder Schriftzüge

    Antworte nur mit dem JSON-Objekt, nichts anderes.
    """

    try:
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')

        payload = {
            "model": "gemma3:4b",
            "prompt": prompt,
            "images": [encoded_image],
            "stream": False
        }

        response = requests.post(
            OLLAMA_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120
        )

        if response.status_code == 200:
            lines = response.text.strip().split("\n")
            combined_response = ""
            for line in lines:
                try:
                    part = json.loads(line)
                    if 'response' in part:
                        combined_response += part['response']
                except json.JSONDecodeError:
                    continue
            return combined_response.strip()
        else:
            print(f"Fehler bei Ollama-API: {response.status_code} - {response.text}")
            return ""
    except Exception as e:
        print(f"Fehler bei Ollama-Analyse: {e}")
        return ""

def categorize(tags_dict):
    # Erstelle flache Liste aller Tags
    all_tags = []
    for key in ['numbers', 'colors', 'texts']:
        if key in tags_dict and isinstance(tags_dict[key], list):
            all_tags.extend([str(tag).lower() for tag in tags_dict[key]])

    # Prüfe auf Kategorien
    for keyword, folder in TAG_CATEGORIES.items():
        if any(keyword in tag for tag in all_tags):
            return folder
    return "Sonstige"

def process_images():
    init_db()
    os.makedirs(DONE_BASE, exist_ok=True)

    for file in os.listdir(IMPORT_DIR):
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            src_path = os.path.join(IMPORT_DIR, file)
            print(f"\nAnalysiere: {file}")

            # Bild analysieren
            raw_response = ollama_analyze_image(src_path)

            # Strukturierte Daten extrahieren
            structured_data = extract_structured_data(raw_response)

            # Beschreibung und Tags holen
            description = structured_data.get("description", raw_response)
            numbers = structured_data.get("numbers", [])
            colors = structured_data.get("colors", [])
            texts = structured_data.get("texts", [])

            # Alle Tags kombinieren für bessere Kategorisierung
            all_tags = list(set(numbers + colors + texts))

            # Kategorie bestimmen
            category = categorize(structured_data)

            # Zielordner erstellen und Bild verschieben
            dest_folder = os.path.join(DONE_BASE, category)
            os.makedirs(dest_folder, exist_ok=True)
            dest_path = os.path.join(dest_folder, file)

            shutil.move(src_path, dest_path)

            # In Datenbank speichern (mit Tags als Teil der Beschreibung)
            tags_info = f"Numbers: {numbers}, Colors: {colors}, Texts: {texts}"
            full_description = f"{description}\n\nTags: {tags_info}"

            save_image(file, dest_path, category, full_description)
            print(f"✔ Verschoben nach {category}")
            print(f"Tags: {all_tags}")

if __name__ == "__main__":
    process_images()