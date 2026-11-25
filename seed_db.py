import sqlite3
import os

# 删掉旧库，确保表结构是新的
if os.path.exists("demo.db"):
    os.remove("demo.db")

# 在当前目录创建样例数据库，并定义销售记录的字段。
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

# 样例涵盖不同商品、日期、金额与件数，供查数和回归评测使用。
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
# 用参数化语句批量插入样例，再提交事务和关闭连接。
cur.executemany(
    "INSERT INTO sales (product, amount, quantity, sale_date) VALUES (?, ?, ?, ?)",
    data
)
conn.commit()
conn.close()
print("demo.db 已重建，含 quantity 字段")