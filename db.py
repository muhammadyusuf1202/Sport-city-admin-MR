import sqlite3

db_path = "sport_city.db"  # sening DB fayling nomi

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# size_available ustuni mavjudligini tekshirish
try:
    cur.execute("ALTER TABLE products ADD COLUMN size_available INTEGER DEFAULT 0")
    print("✅ size_available ustuni qo‘shildi.")
except sqlite3.OperationalError:
    print("ℹ size_available ustuni allaqachon mavjud.")

# size ustuni mavjudligini tekshirish
try:
    cur.execute("ALTER TABLE products ADD COLUMN size TEXT")
    print("✅ size ustuni qo‘shildi.")
except sqlite3.OperationalError:
    print("ℹ size ustuni allaqachon mavjud.")

conn.commit()
conn.close()
print("✔ Jadval yangilandi!")
