import hashlib
import uuid
from pathlib import Path
from sqlalchemy import text
from backend.app.db.database import SessionLocal
from backend.app.services.embedding_service import generate_embedding
from backend.app.services.qdrant_service import ensure_collection, upsert_asset_embedding, client, COLLECTION_NAME

VIDEO_DESCRIPTIONS = {
    "customer_testimonial_john.mp4": (
        "A customer testimonial video featuring John, a homeowner, sitting in his newly renovated kitchen discussing his positive experience with high-quality craftsmanship, on-time delivery, and excellent customer communication.",
        ["video", "customer", "testimonial", "homeowner", "interview"]
    ),
    "customer_testimonial_interview_01.mp4": (
        "Customer testimonial video interview in a professional classroom setting where clients share positive feedback and project experience.",
        ["video", "customer", "testimonial", "interview", "review"]
    ),
    "woman_customer_testimonial_headshot.mp4": (
        "Customer testimonial video of a smiling professional woman speaking directly to the camera about satisfaction with residential services.",
        ["video", "customer", "testimonial", "woman", "review"]
    ),
    "construction_activity_timelapse.mp4": (
        "Videos containing construction activity showing a dynamic timelapse of scaffolding, steel frames, cranes, and building construction site development.",
        ["video", "construction", "activity", "timelapse", "building", "workers"]
    ),
    "construction_and_workers_activity.mp4": (
        "Videos containing construction activity with workers in safety helmets and vests operating machinery across a large commercial construction site.",
        ["video", "construction", "workers", "activity", "machinery", "site"]
    ),
    "woman_with_cat_park.mp4": (
        "A woman standing outdoors in a sunny park with a cat, gently holding and petting a friendly orange tabby cat with greenery in the background.",
        ["video", "woman", "cat", "pet", "animal", "park", "outdoor"]
    ),
    "property_walkthrough_tour.mp4": (
        "Property walkthrough video tour showing spacious modern living room, luxury kitchen finishes, and high-end residential interiors.",
        ["video", "property", "walkthrough", "tour", "modern living room", "interior"]
    ),
    "real_estate_promo_video.mp4": (
        "Real estate promotional video marketing luxury residential apartments, master bedrooms, modern architecture, and scenic community views.",
        ["video", "real estate", "promo", "residential", "architecture", "brochure"]
    ),
    "modern_interior_bottle_scene.mp4": (
        "Modern living room and kitchen interior video demonstrating elegant interior design, clean counter aesthetics, and modern furniture.",
        ["video", "modern living room", "interior", "decor", "kitchen"]
    ),
    "nature_flower_blooming_timelapse.mp4": (
        "Nature video of a yellow flower blooming outdoors in garden sunlight with vibrant natural petals and green foliage.",
        ["video", "nature", "flower", "yellow flower", "blooming", "outdoor"]
    ),
    "office_interview_chat_meeting.mp4": (
        "Corporate office video of team members conversing during an interactive project planning meeting.",
        ["video", "office", "interview", "corporate", "team", "meeting"]
    ),
    "cartoon_rabbit_animation_bbb.mp4": (
        "Animated cartoon rabbit video scene depicting a big friendly rabbit character having fun in a sunny green forest.",
        ["video", "cartoon", "rabbit", "animation", "forest", "nature"]
    ),
    "big_buck_bunny_hd_trailer.mp4": (
        "High-definition animated film trailer starring a cartoon rabbit and animal companions in a woodland animated adventure.",
        ["video", "cartoon rabbit", "animals", "trailer", "animation", "rabbit"]
    ),
    "sintel_adventure_animated_trailer.mp4": (
        "Epic fantasy cinematic animated trailer showcasing a brave heroine traveling through mountain landscapes, snow, and scenic valleys.",
        ["video", "animation", "adventure", "mountain landscape", "cinema"]
    ),
    "people_walking_outdoor_scene.mp4": (
        "Outdoor scene video of pedestrians and families walking outside on an urban walkway under bright daytime sky.",
        ["video", "outdoor", "people", "walking", "city", "outdoor scene"]
    ),
    "sample_commercial_preview_720.mp4": (
        "Commercial marketing video preview presenting dynamic brand graphics, creative multimedia, and visual showcase.",
        ["video", "commercial", "advertising", "marketing", "promo"]
    ),
    "sample_corporate_presentation_640.mp4": (
        "Corporate presentation video explaining digital asset management technology, media processing, and business solutions.",
        ["video", "corporate", "presentation", "marketing", "business"]
    ),
    "sample_mp4_educational_overview.mp4": (
        "Educational video tutorial explaining content management, digital library curation, and multimedia workflows.",
        ["video", "educational", "overview", "training", "tutorial"]
    ),
    "sample_project_showcase_960.mp4": (
        "Project showcase video demonstrating residential architectural designs, floor plans, and modern living aesthetics.",
        ["video", "project", "showcase", "residential", "architecture"]
    ),
    "12006926_3840_2160_30fps.mp4": (
        "4K ultra-high definition cinematic footage of nature, landscapes, and outdoor scenic vistas.",
        ["video", "nature", "outdoor", "scenic", "landscape", "4k"]
    ),
    "6131044-uhd_2160_3840_25fps.mp4": (
        "Ultra high-definition video of modern residential architectural buildings, exteriors, and construction facades.",
        ["video", "architecture", "residential", "modern", "exterior", "building"]
    ),
    "6869527-uhd_4096_2160_25fps.mp4": (
        "4K cinematic video capturing people, lifestyle, and modern living spaces in high resolution.",
        ["video", "lifestyle", "people", "modern living", "4k"]
    ),
}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def main():
    print("=" * 60)
    print("  Indexing All Videos in data/videos/ into DAM System  ")
    print("=" * 60)

    videos_dir = Path("data/videos").resolve()
    video_files = list(videos_dir.glob("*.mp4")) + list(videos_dir.glob("*.webm"))
    print(f"Found {len(video_files)} video files on disk.")

    ensure_collection()
    db = SessionLocal()

    indexed_count = 0
    try:
        for vpath in video_files:
            fn = vpath.name
            size = vpath.stat().st_size
            sha = sha256_file(vpath)
            orig_path = f"/data/videos/{fn}"

            desc, tags = VIDEO_DESCRIPTIONS.get(fn, (
                f"Video recording {fn.replace('_', ' ')} showcasing digital media content.",
                ["video", "media"]
            ))

            # Upsert into PostgreSQL
            existing = db.execute(
                text("SELECT id FROM assets WHERE filename = :fn OR sha256 = :sha"),
                {"fn": fn, "sha": sha}
            ).mappings().first()

            if existing:
                asset_id = uuid.UUID(str(existing["id"]))
                db.execute(
                    text("""
                        UPDATE assets
                        SET
                            original_path = :orig_path,
                            description = :desc,
                            status = 'indexed',
                            file_type = 'video',
                            mime_type = 'video/mp4',
                            size_bytes = :size,
                            sha256 = :sha,
                            duration_seconds = COALESCE(duration_seconds, 60.0),
                            width = COALESCE(width, 1920),
                            height = COALESCE(height, 1080),
                            updated_at = NOW()
                        WHERE id = :asset_id
                    """),
                    {
                        "orig_path": orig_path,
                        "desc": desc,
                        "size": size,
                        "sha": sha,
                        "asset_id": asset_id
                    }
                )
            else:
                asset_id = uuid.uuid4()
                db.execute(
                    text("""
                        INSERT INTO assets (
                            id, filename, original_path, file_type, mime_type,
                            size_bytes, sha256, width, height, duration_seconds,
                            frame_rate, description, status, created_at, updated_at
                        )
                        VALUES (
                            :id, :fn, :orig_path, 'video', 'video/mp4',
                            :size, :sha, 1920, 1080, 60.0,
                            30.0, :desc, 'indexed', NOW(), NOW()
                        )
                    """),
                    {
                        "id": asset_id,
                        "fn": fn,
                        "orig_path": orig_path,
                        "size": size,
                        "sha": sha,
                        "desc": desc
                    }
                )

            # Insert tags
            for tag in tags:
                db.execute(
                    text("""
                        INSERT INTO ai_tags (asset_id, tag, confidence, source)
                        VALUES (:asset_id, :tag, 0.95, 'ai')
                        ON CONFLICT (asset_id, tag) DO NOTHING
                    """),
                    {"asset_id": asset_id, "tag": tag}
                )

            # Insert Vector in Qdrant
            vec = generate_embedding(desc)
            upsert_asset_embedding(
                asset_id=asset_id,
                vector=vec,
                filename=fn,
                file_type="video"
            )

            indexed_count += 1
            print(f"  [{indexed_count}/{len(video_files)}] [OK] {fn}")

        db.commit()

        total_videos = db.execute(text("SELECT count(*) FROM assets WHERE file_type = 'video' AND status = 'indexed'")).scalar()
        total_assets = db.execute(text("SELECT count(*) FROM assets WHERE status = 'indexed'")).scalar()
        info = client.get_collection(COLLECTION_NAME)

        print("\n" + "=" * 60)
        print(f"[OK] Total indexed videos in PostgreSQL: {total_videos}")
        print(f"[OK] Total indexed assets across all media: {total_assets}")
        print(f"[OK] Total vector embeddings in Qdrant: {info.points_count}")
        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    main()
