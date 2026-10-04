"""Diagnostic script - check embedding quality and search accuracy."""
import sys
import os
import socket
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
os.environ["PYTHONIOENCODING"] = "utf-8"

# Force UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from backend.app.db.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# 1. Ollama
print("=" * 60)
print("1. OLLAMA STATUS")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    res = sock.connect_ex(("localhost", 11434))
    sock.close()
    print(f"   Ollama port 11434: {'ONLINE' if res == 0 else 'OFFLINE - using fallback hashing!'}")
except Exception as e:
    print(f"   Ollama check failed: {e}")

# 2. Qdrant
print("\n2. QDRANT STATUS")
try:
    from qdrant_client import QdrantClient
    qc = QdrantClient(url="http://localhost:6333")
    info = qc.get_collection("asset_embeddings")
    print(f"   Points count: {info.points_count}")
    print(f"   Vector size: {info.config.params.vectors.size}")
    print(f"   Distance: {info.config.params.vectors.distance}")
except Exception as e:
    print(f"   Qdrant error: {e}")

# 3. Asset descriptions
print("\n3. ASSET STATUS SUMMARY")
status_rows = db.execute(text("""
    SELECT status, file_type, count(*) as cnt
    FROM assets
    GROUP BY status, file_type
    ORDER BY status, file_type
""")).mappings().all()
for r in status_rows:
    print(f"   {r['status']:15} {r['file_type']:8} count={r['cnt']}")

print("\n4. SAMPLE DESCRIPTIONS")
rows = db.execute(text("""
    SELECT filename, file_type, status,
           length(description) as desc_len,
           left(description, 120) as desc_preview
    FROM assets
    WHERE description IS NOT NULL
    ORDER BY file_type, filename
    LIMIT 15
""")).mappings().all()

for r in rows:
    desc = (r['desc_preview'] or '').replace('\n', ' ')
    print(f"   [{r['file_type']:5}] {r['filename'][:38]:38} | {desc[:80]}")

null_count = db.execute(text("SELECT count(*) FROM assets WHERE description IS NULL")).scalar()
total_count = db.execute(text("SELECT count(*) FROM assets")).scalar()
print(f"\n   Total: {total_count}, No description: {null_count}")

# 4. Embedding similarity test (fallback)
print("\n5. FALLBACK EMBEDDING SIMILARITY TEST")
from backend.app.services.embedding_service import _fallback_embedding

test_cases = [
    ("woman standing with a cat", "A woman in a sunny park with a cat, gently holding orange tabby cat"),
    ("construction activity workers", "Construction site with workers in hard hats building"),
    ("modern living room interior", "Modern living room and kitchen interior elegant design clean aesthetics"),
    ("customer testimonial video", "Customer testimonial video John homeowner positive experience communication"),
    ("yellow flower garden", "Yellow flower bloom garden nature scene"),
    ("mountain landscape outdoor", "Mountain landscape snow peaks outdoor scenic photography"),
    ("PDF brochure residential project", "Residential project brochure luxury apartments amenities"),
]

print("   Cosine similarities (higher = better match):")
for query, relevant_desc in test_cases:
    qv = np.array(_fallback_embedding(query))
    dv = np.array(_fallback_embedding(relevant_desc))
    sim = float(np.dot(qv, dv))
    quality = "GOOD" if sim > 0.3 else ("OK" if sim > 0.15 else "BAD")
    print(f"   [{quality}] {sim:.4f}  '{query[:35]:35}' <-> relevant desc")

db.close()
print("\n" + "=" * 60)
print("DIAGNOSIS COMPLETE")
