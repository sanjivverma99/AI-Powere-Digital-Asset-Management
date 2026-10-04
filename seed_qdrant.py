from sqlalchemy import text
from backend.app.db.database import SessionLocal
from backend.app.services.embedding_service import generate_embedding
from backend.app.services.qdrant_service import ensure_collection, upsert_asset_embedding, client, COLLECTION_NAME
from uuid import UUID

def seed():
    ensure_collection()
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, filename, file_type, description FROM assets WHERE status = 'indexed'")).mappings().all()
        print(f"Found {len(rows)} indexed assets in Postgres to sync into Qdrant.")
        for row in rows:
            asset_id = UUID(str(row["id"]))
            desc = row["description"] or row["filename"]
            vec = generate_embedding(desc)
            upsert_asset_embedding(
                asset_id=asset_id,
                vector=vec,
                filename=row["filename"],
                file_type=row["file_type"]
            )
            print(f"Synced {row['filename']} ({row['file_type']}) into Qdrant.")
        
        info = client.get_collection(COLLECTION_NAME)
        print(f"Collection status: points_count={info.points_count}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
