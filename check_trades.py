#!/usr/bin/env python3
import sqlite3, os
db = "data/trade_history.db"
print("DB exists:", os.path.exists(db))
if os.path.exists(db):
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM trades")
    print("Total trades:", c.fetchone()[0])
    c.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT 5")
    for r in c.fetchall():
        print(r)
    conn.close()
else:
    print("No trade_history.db found")
