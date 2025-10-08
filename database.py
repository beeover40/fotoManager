import sqlite3

DB_NAME = "images.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            path TEXT,
            category TEXT,
            description TEXT,
            moved BOOLEAN DEFAULT FALSE
        )
    """)
    conn.commit()
    conn.close()

def save_image(filename, path, category, description):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO images (filename, path, category, description)
        VALUES (?, ?, ?, ?)
    """, (filename, path, category, description))
    conn.commit()
    conn.close()