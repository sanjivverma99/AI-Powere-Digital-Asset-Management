"""Index all pending / non-indexed assets into MongoDB and Qdrant."""
import sys
from uuid import UUID
from backend.app.db.database import assets_collection
from backend.app.services.indexing_service import index_asset
from backend.app.services.qdrant_service import get_collection_info

def main():
    pending = list(assets_collection.find({"status": {"$ne": "indexed"}}, {"_id": 0, "id": 1, "filename": 1, "file_type": 1}))
    print(f"Found {len(pending)} assets to index...")
    
    success, failed = 0, 0
    for idx, asset in enumerate(pending, 1):
        asset_id = UUID(str(asset["id"]))
        filename = asset["filename"]
        file_type = asset["file_type"]
        try:
            res = index_asset(asset_id)
            success += 1
            if idx % 20 == 0 or idx == len(pending):
                print(f"[{idx:3}/{len(pending)}] Indexed: {file_type:5} {filename[:35]}")
        except Exception as e:
            failed += 1
            print(f"[{idx:3}/{len(pending)}] FAILED: {filename} -> {e}")
            
    print("=" * 60)
    print(f"Indexing complete! Success: {success}, Failed: {failed}")
    print(f"Total in MongoDB: {assets_collection.count_documents({'status': 'indexed'})}")
    try:
        info = get_collection_info()
        print(f"Qdrant points count: {info.points_count}")
    except Exception as e:
        print(f"Qdrant info error: {e}")

if __name__ == "__main__":
    main()
