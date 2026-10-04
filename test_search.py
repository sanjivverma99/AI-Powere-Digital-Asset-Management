import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from backend.app.services.search_service import search_assets

queries = [
    "A woman standing with a cat",
    "Customer testimonial videos",
    "Brochures related to residential projects",
    "Images showing a modern living room",
    "Videos containing construction activity",
    "construction site",
    "people walking"
]

for q in queries:
    print(f"\n======================================")
    print(f"QUERY: '{q}'")
    print(f"======================================")
    results = search_assets(q, limit=3)
    if not results:
        print("  [!] No results found")
    for idx, r in enumerate(results, 1):
        score = r.get("score", 0)
        fname = r.get("filename")
        ftype = r.get("file_type")
        desc = (r.get("description") or "").replace("\n", " ")[:90]
        print(f"  #{idx} [{score:.3f}] ({ftype}) {fname}\n      Desc: {desc}")
