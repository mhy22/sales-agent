import sqlite3
import os

# 删掉旧库，确保表结构是新的
if os.path.exists("demo.db"):
    os.remove("demo.db")

conn = sqlite3.connect("demo.db")
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY,
    product TEXT,
    amount REAL,
    quantity INTEGER,
    sale_date TEXT
)
""")

data = [
    ("笔记本", 1200, 1, "2026-09-03"),
    ("笔记本", 1500, 1, "2026-09-15"),
    ("鼠标", 80, 2, "2026-09-05"),
    ("键盘", 300, 1, "2026-10-01"),
    ("键盘", 350, 1, "2026-10-12"),
    ("显示器", 900, 1, "2026-10-20"),
    ("鼠标", 90, 3, "2026-10-22"),
    ("笔记本", 1800, 1, "2026-10-25"),
]
cur.executemany(
    "INSERT INTO sales (product, amount, quantity, sale_date) VALUES (?, ?, ?, ?)",
    data
)
conn.commit()
conn.close()
print("demo.db 已重建，含 quantity 字段")