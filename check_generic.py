"""Check generic descriptions."""
import sys
sys.path.insert(0, '.')
from backend.app.db.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
rows = db.execute(text("SELECT filename, file_type, left(description,150) as desc FROM assets WHERE description LIKE 'Sample photograph%' ORDER BY filename")).mappings().all()
for r in rows:
    print(f"{r['filename'][:45]:45} | {r['desc']}")
total = db.execute(text("SELECT count(*) FROM assets WHERE description LIKE 'Sample photograph%'")).scalar()
print(f"\nTotal generic template descriptions: {total}")
db.close()
