from flask import Flask, render_template, request, send_from_directory, jsonify
import sqlite3
import os
import json
import threading
import time
from werkzeug.utils import secure_filename

app = Flask(__name__)
DB_NAME = "images.db"
IMAGE_FOLDER = "03_Done"

# Konfiguration für Uploads
UPLOAD_FOLDER = "01_Import"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Stelle sicher, dass Ordner existieren
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)

def parse_tags_from_description(description):
    """Extrahiert Tags aus der Beschreibung"""
    tags = {
        "numbers": [],
        "colors": [],
        "texts": []
    }

    if "Tags:" in description:
        try:
            tags_part = description.split("Tags:")[1].strip()

            if "Numbers:" in tags_part:
                numbers_start = tags_part.find("Numbers:") + 9
                numbers_end = tags_part.find("]", numbers_start) + 1
                numbers_str = tags_part[numbers_start:numbers_end]
                tags["numbers"] = eval(numbers_str) if numbers_str else []

            if "Colors:" in tags_part:
                colors_start = tags_part.find("Colors:") + 8
                colors_end = tags_part.find("]", colors_start) + 1
                colors_str = tags_part[colors_start:colors_end]
                tags["colors"] = eval(colors_str) if colors_str else []

            if "Texts:" in tags_part:
                texts_start = tags_part.find("Texts:") + 7
                texts_end = tags_part.find("]", texts_start) + 1
                texts_str = tags_part[texts_start:texts_end]
                tags["texts"] = eval(texts_str) if texts_str else []

        except Exception as e:
            print(f"Fehler beim Parsen der Tags: {e}")

    return tags

@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    category_filter = request.args.get("category", "").strip()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    sql = """
        SELECT id, filename, path, category, description
        FROM images
        WHERE 1=1
    """
    params = []

    if query:
        sql += """ AND (
            filename LIKE ? 
            OR description LIKE ? 
            OR category LIKE ?
        )"""
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

    if category_filter:
        sql += " AND category = ?"
        params.append(category_filter)

    sql += " ORDER BY id DESC"

    cursor.execute(sql, params)
    results = cursor.fetchall()
    conn.close()

    processed_results = []
    categories = set()

    for row in results:
        id_, filename, path, category, description = row
        categories.add(category)

        main_description = description.split("\n\nTags:")[0] if "\n\nTags:" in description else description
        tags = parse_tags_from_description(description)

        processed_results.append({
            "id": id_,
            "filename": filename,
            "path": path,
            "category": category,
            "description": main_description,
            "tags": tags
        })

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM images")
    all_categories = [row[0] for row in cursor.fetchall()]
    conn.close()

    return render_template(
        "gallery.html", 
        results=processed_results, 
        query=query,
        category_filter=category_filter,
        categories=all_categories
    )

@app.route("/upload", methods=["POST"])
def upload_file():
    """Handle Drag-and-Drop Upload"""
    if 'file' not in request.files:
        return jsonify({"error": "Keine Datei gefunden"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Keine Datei ausgewählt"}), 400

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({"success": True, "filename": filename})

@app.route("/process-images", methods=["POST"])
def trigger_processing():
    """Trigger image categorization"""
    try:
        # Importiere den Kategorisierer dynamisch
        import sys
        import importlib.util

        # Pfad zum Kategorisierer-Skript
        spec = importlib.util.spec_from_file_location("processor", "process_images.py")
        processor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(processor)

        # Führe die Verarbeitung in einem separaten Thread aus
        def run_processing():
            try:
                processor.process_images()
            except Exception as e:
                print(f"Fehler bei der Verarbeitung: {e}")

        thread = threading.Thread(target=run_processing)
        thread.start()

        return jsonify({"success": True, "message": "Verarbeitung gestartet"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/processing-status")
def processing_status():
    """Prüfe Verarbeitungsstatus"""
    import os
    files_in_import = len([f for f in os.listdir(UPLOAD_FOLDER) 
                          if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    return jsonify({"files_to_process": files_in_import})

@app.route("/api/tags/<int:image_id>")
def get_image_tags(image_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT description FROM images WHERE id = ?", (image_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        tags = parse_tags_from_description(row[0])
        return {"tags": tags}
    return {"tags": {}}

@app.route("/03_Done/<path:folder>/<filename>")
def serve_image(folder, filename):
    return send_from_directory(os.path.join("03_Done", folder), filename)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)