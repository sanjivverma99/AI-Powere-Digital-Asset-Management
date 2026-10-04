from pathlib import Path
from uuid import UUID
from sqlalchemy import text

from backend.app.db.database import SessionLocal
from backend.app.services.scanner_service import scan_library
from backend.app.services.embedding_service import generate_embedding
from backend.app.services.qdrant_service import ensure_collection, upsert_asset_embedding, client, COLLECTION_NAME

def main():
    print("[1/3] Scanning data library...")
    stats = scan_library("data")
    print(f"Scan completed: {stats}")

    print("[2/3] Updating asset status and descriptions in Postgres...")
    db = SessionLocal()
    try:
        pending_rows = db.execute(
            text("""
                SELECT id, filename, file_type, width, height, original_path 
                FROM assets 
                WHERE status = 'pending'
            """)
        ).mappings().all()
        print(f"Found {len(pending_rows)} pending assets to process.")

        ensure_collection()

        count = 0
        for row in pending_rows:
            asset_id = UUID(str(row["id"]))
            filename = row["filename"]
            file_type = row["file_type"]
            w = row["width"] or 0
            h = row["height"] or 0

            # Generate natural descriptive metadata
            clean_name = filename.replace("_", " ").replace("-", " ").replace(".jpg", "").replace(".png", "")
            desc = f"Sample photograph {clean_name}, high resolution {w}x{h} px from Pixabay collection."

            db.execute(
                text("""
                    UPDATE assets 
                    SET description = :desc, status = 'indexed', updated_at = NOW() 
                    WHERE id = :asset_id
                """),
                {"desc": desc, "asset_id": asset_id}
            )

            # Insert AI tags
            tags = ["sample", "pixabay", "photography", file_type]
            if w > h:
                tags.append("landscape")
            elif h > w:
                tags.append("portrait")
            for tag in tags:
                db.execute(
                    text("""
                        INSERT INTO ai_tags (asset_id, tag, confidence, source)
                        VALUES (:asset_id, :tag, 0.9, 'ai')
                        ON CONFLICT (asset_id, tag) DO NOTHING
                    """),
                    {"asset_id": asset_id, "tag": tag}
                )

            # Upsert vector embedding into Qdrant
            vec = generate_embedding(desc)
            upsert_asset_embedding(
                asset_id=asset_id,
                vector=vec,
                filename=filename,
                file_type=file_type
            )
            count += 1
            if count % 25 == 0:
                print(f"Indexed {count}/{len(pending_rows)} assets into Qdrant & Postgres...")

        db.commit()
        print(f"[3/3] Successfully processed and indexed {count} new assets!")

        info = client.get_collection(COLLECTION_NAME)
        total_assets = db.execute(text("SELECT count(*) FROM assets WHERE status = 'indexed'")).scalar()
        print(f"Total indexed assets in PostgreSQL: {total_assets}")
        print(f"Total vector embeddings in Qdrant: {info.points_count}")

    finally:
        db.close()

if __name__ == "__main__":
    main()
