from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID
from uuid import uuid4

from pymongo import ReturnDocument

from backend.app.db.database import (
    assets_collection,
    indexing_jobs_collection,
    utc_now,
)
from backend.app.services.embedding_service import generate_embedding
from backend.app.services.ollama_service import (
    generate_image_description,
    generate_video_description,
)
from backend.app.services.pdf_service import extract_pdf_text
from backend.app.services.qdrant_service import upsert_asset_embedding
from backend.app.services.video_service import extract_video_frames


# ── Semantic taxonomy & keyword mapping ──────────────────────────────────────
_TAXONOMY: dict[str, dict[str, Any]] = {
    "flower": {
        "desc": "Close-up photograph of vibrant flowers in bloom with colorful petals, lush green foliage, and natural sunlight. Floral botanical nature photography.",
        "tags": ["flower", "flowers", "flora", "bloom", "blooming", "petals", "plant", "nature", "botanical", "garden", "outdoor"],
    },
    "rose": {
        "desc": "Beautiful rose flower in full bloom with rich red or pink petals. Macro floral photography capturing delicate petals and natural garden beauty.",
        "tags": ["rose", "flower", "flowers", "bloom", "flora", "red", "pink", "garden", "nature", "botanical", "petals"],
    },
    "sunflower": {
        "desc": "Bright yellow sunflower with large golden petals and brown center disc standing tall in a sunny field. Summer botanical photography.",
        "tags": ["sunflower", "flower", "yellow", "golden", "nature", "flora", "bloom", "summer", "field", "outdoor", "botanical"],
    },
    "tulip": {
        "desc": "Colorful tulip flowers in bloom showcasing vivid garden beauty with elegant petals.",
        "tags": ["tulip", "tulips", "flower", "flowers", "spring", "garden", "nature", "flora", "bloom", "colorful"],
    },
    "garden": {
        "desc": "Outdoor garden scene with flowering plants, colorful blooms, landscaping, and lush green vegetation.",
        "tags": ["garden", "plants", "flowers", "greenery", "nature", "outdoor", "landscape", "botanical"],
    },
    "forest": {
        "desc": "Woodland forest scene with tall trees, lush green foliage, and dappled sunlight filtering through leaves.",
        "tags": ["forest", "trees", "woodland", "nature", "green", "outdoor", "landscape", "canopy"],
    },
    "tree": {
        "desc": "Natural outdoor scene featuring tall trees with lush green canopy in a park or forest.",
        "tags": ["tree", "trees", "forest", "nature", "outdoor", "greenery", "landscape", "park"],
    },
    "mountain": {
        "desc": "Dramatic mountain landscape with towering rocky peaks, snow coverage, clear sky, and scenic panoramic views.",
        "tags": ["mountain", "mountains", "landscape", "peaks", "snow", "outdoor", "scenic", "nature", "rocky", "panoramic"],
    },
    "lake": {
        "desc": "Scenic lake landscape with calm reflective water surrounded by trees or mountains in natural daylight.",
        "tags": ["lake", "water", "nature", "landscape", "reflection", "outdoor", "scenic", "calm"],
    },
    "river": {
        "desc": "Flowing river through natural landscape with rocky banks, clear water, and surrounding greenery.",
        "tags": ["river", "water", "nature", "landscape", "stream", "flow", "outdoor", "scenic"],
    },
    "beach": {
        "desc": "Sandy beach coastal scene with ocean waves, blue water, sandy shore, and sunny horizon.",
        "tags": ["beach", "ocean", "sea", "sand", "coast", "coastal", "waves", "water", "outdoor", "summer"],
    },
    "ocean": {
        "desc": "Vast ocean or sea scene with waves, deep blue water, and coastal horizon views.",
        "tags": ["ocean", "sea", "water", "waves", "blue", "coastal", "marine", "nature", "outdoor"],
    },
    "sunset": {
        "desc": "Beautiful sunset scene with warm orange, pink, and golden sky colors over the horizon.",
        "tags": ["sunset", "sky", "sun", "golden", "orange", "warm", "evening", "horizon", "nature", "scenic", "outdoor"],
    },
    "sunrise": {
        "desc": "Scenic sunrise with warm golden tones, pink sky, and sun emerging over the horizon in early morning.",
        "tags": ["sunrise", "morning", "sun", "sky", "golden", "dawn", "nature", "scenic", "outdoor"],
    },
    "sky": {
        "desc": "Scenic sky photograph with dramatic clouds, blue atmosphere, and open weather conditions.",
        "tags": ["sky", "clouds", "blue", "atmosphere", "outdoor", "weather", "scenic", "nature"],
    },
    "snow": {
        "desc": "Winter snow scene with white snow-covered ground, frosty trees, and cold scenic landscape.",
        "tags": ["snow", "winter", "cold", "frost", "white", "landscape", "nature", "outdoor", "ice"],
    },
    "waterfall": {
        "desc": "Scenic waterfall with cascading water flowing over rocks into a crystal pool below.",
        "tags": ["waterfall", "water", "cascade", "nature", "rocky", "landscape", "outdoor", "scenic"],
    },
    "cat": {
        "desc": "Cat portrait featuring a domestic feline cat with distinctive fur patterns, whiskers, and expressive eyes. Animal pet photography.",
        "tags": ["cat", "portrait", "animal", "pet", "feline", "kitten", "mammal", "domestic", "whiskers"],
    },
    "dog": {
        "desc": "Dog photograph showing a domestic canine pet, playing, sitting, or running in an outdoor or indoor setting.",
        "tags": ["dog", "canine", "pet", "animal", "puppy", "hound", "domestic", "mammal"],
    },
    "bird": {
        "desc": "Bird wildlife photography showing a bird perched or in flight in a natural outdoor setting.",
        "tags": ["bird", "avian", "wildlife", "animal", "feathers", "wings", "flight", "nature", "outdoor"],
    },
    "horse": {
        "desc": "Photograph of a majestic horse in a pasture, stable, or equestrian field.",
        "tags": ["horse", "equine", "animal", "stallion", "field", "farm", "pasture", "mammal"],
    },
    "animal": {
        "desc": "Wildlife or domestic animal photograph capturing creature in its natural habitat or portrait.",
        "tags": ["animal", "wildlife", "creature", "pet", "fauna", "nature", "mammal"],
    },
    "wildlife": {
        "desc": "Wildlife nature photography capturing animals in their natural wilderness habitat.",
        "tags": ["wildlife", "animals", "animal", "nature", "wilderness", "fauna", "outdoor"],
    },
    "living": {
        "desc": "Living room interior photograph showing comfortable modern seating, sofas, decorative elements, and clean home decor.",
        "tags": ["living room", "living", "room", "interior", "modern", "home", "furniture", "sofa", "decor", "indoor", "design"],
    },
    "kitchen": {
        "desc": "Modern kitchen interior design with countertops, appliances, cabinetry, island, and contemporary aesthetic.",
        "tags": ["kitchen", "interior", "modern", "countertops", "appliances", "cabinetry", "home", "indoor", "design", "cook"],
    },
    "bedroom": {
        "desc": "Bedroom interior photograph with bed, pillows, lighting, and comfortable modern interior decoration.",
        "tags": ["bedroom", "bed", "interior", "room", "home", "furniture", "indoor", "decor", "comfort"],
    },
    "apartment": {
        "desc": "Modern apartment building or luxury residential interior and exterior architecture with contemporary finishes.",
        "tags": ["apartment", "luxury", "interior", "residential", "building", "home", "property", "modern", "architecture"],
    },
    "luxury": {
        "desc": "Luxury high-end residential interior or architectural design with premium finishes and elegant decor.",
        "tags": ["luxury", "premium", "apartment", "interior", "elegant", "design", "property", "architecture"],
    },
    "residential": {
        "desc": "Residential building or housing development property showing home architecture and surroundings.",
        "tags": ["residential", "housing", "property", "building", "architecture", "home", "real estate"],
    },
    "building": {
        "desc": "Architectural photograph of a building exterior showing structural design, facade, and urban environment.",
        "tags": ["building", "architecture", "facade", "urban", "construction", "structure", "city"],
    },
    "construction": {
        "desc": "Active construction site with building materials, scaffolding, heavy equipment, and workers in hard hats building structures.",
        "tags": ["construction", "site", "workers", "worker", "building", "scaffolding", "activity", "industrial", "contractor"],
    },
    "worker": {
        "desc": "Workers and employees in professional or industrial work environment on site.",
        "tags": ["worker", "workers", "people", "working", "labor", "industrial", "site", "outdoor"],
    },
    "aerial": {
        "desc": "Aerial or overhead photograph showing bird's eye view of buildings, landscape, cityscape, or construction area.",
        "tags": ["aerial", "overhead", "drone", "view", "buildings", "city", "skyline", "landscape", "urban"],
    },
    "skyline": {
        "desc": "Urban city skyline photograph showing skyscrapers, high-rise buildings, and metropolitan architecture.",
        "tags": ["skyline", "city", "urban", "skyscrapers", "towers", "buildings", "architecture", "metropolitan"],
    },
    "testimonial": {
        "desc": "Customer testimonial video with client speaking about positive experience, project results, and communication.",
        "tags": ["testimonial", "customer", "interview", "video", "client", "review", "experience", "speaking"],
    },
    "customer": {
        "desc": "Customer interaction and client feedback testimonial video or photograph.",
        "tags": ["customer", "testimonial", "client", "interaction", "business", "service"],
    },
    "brochure": {
        "desc": "Project brochure and document detailing residential developments, specifications, amenities, and floorplans.",
        "tags": ["brochure", "residential", "project", "pdf", "document", "specifications", "amenities", "details"],
    },
    "document": {
        "desc": "Document with technical specifications, project details, reports, and structured content.",
        "tags": ["document", "pdf", "technical", "content", "report", "text", "specifications"],
    },
}


def _extract_tags_from_text(text: str) -> list[str]:
    """Extract normalized unique keywords and tags from a text string."""
    cleaned = re.sub(r'[^a-zA-Z0-9\s\-]', ' ', text.lower())
    words = [w.strip('-') for w in cleaned.split() if len(w) > 2]
    tags = list(dict.fromkeys(words))
    return tags[:25]


def _analyze_image_pixels(img_path: Path) -> dict:
    """Analyze actual image pixels for visual features (colors, brightness, composition)."""
    try:
        from PIL import Image
        with Image.open(img_path) as img:
            rgb = img.convert("RGB")
            w, h = rgb.size
            aspect = "portrait" if h > w * 1.15 else ("square" if abs(h - w) < w * 0.1 else "landscape")

            small = rgb.resize((60, 60))
            pixels = list(small.getdata())

            avg_brightness = sum((r + g + b) / 3 for r, g, b in pixels) / len(pixels)
            brightness_label = "dark moody" if avg_brightness < 75 else ("bright well-lit" if avg_brightness > 175 else "natural balanced lighting")

            avg_r = sum(r for r, g, b in pixels) / len(pixels)
            avg_g = sum(g for r, g, b in pixels) / len(pixels)
            avg_b = sum(b for r, g, b in pixels) / len(pixels)

            tones = []
            tags = [aspect, "photography"]

            if avg_b > avg_r * 1.1 and avg_b > avg_g:
                tones.append("cool blue tones")
                tags.extend(["blue", "sky", "water", "cool"])
            elif avg_r > avg_b * 1.2:
                tones.append("warm golden tones")
                tags.extend(["warm", "golden", "orange", "yellow"])
            if avg_g > avg_r * 1.1 and avg_g > avg_b:
                tones.append("lush green natural tones")
                tags.extend(["green", "nature", "plants", "foliage"])
            if not tones:
                tones.append("neutral natural tones")

            return {
                "aspect": aspect,
                "brightness": brightness_label,
                "tones": ", ".join(tones),
                "resolution": f"{w}x{h}",
                "tags": tags,
                "is_bright": avg_brightness > 160,
                "is_green": avg_g > avg_r * 1.15,
                "is_blue": avg_b > avg_r * 1.15,
                "is_warm": avg_r > avg_b * 1.2,
            }
    except Exception:
        return {
            "aspect": "landscape",
            "brightness": "natural lighting",
            "tones": "natural tones",
            "resolution": "",
            "tags": ["image", "visual"],
            "is_bright": False,
            "is_green": False,
            "is_blue": False,
            "is_warm": False,
        }


def _smart_enrich_asset(
    filename: str,
    file_type: str,
    file_path: Path | None = None,
    extracted_text: str | None = None,
) -> tuple[str, list[str]]:
    """
    Generate rich description and comprehensive semantic tags.
    """
    stem = Path(filename).stem.lower()
    words = re.sub(r'[_\-]+', ' ', stem).split()
    clean_words = [w for w in words if len(w) > 2 and not w.isdigit()]

    matched_keys = []
    matched_tags: list[str] = []
    matched_descs = []

    for word in clean_words:
        for key, entry in _TAXONOMY.items():
            if key == word or word.startswith(key) or key.startswith(word):
                if key not in matched_keys:
                    matched_keys.append(key)
                    matched_tags.extend(entry["tags"])
                    matched_descs.append(entry["desc"])

    # Fallback for Pixabay numbered images or generic images
    if not matched_descs and file_type == "image":
        vis = _analyze_image_pixels(file_path) if file_path and file_path.exists() else {}
        matched_tags.extend(vis.get("tags", []))

        if vis.get("is_blue") and vis.get("is_green"):
            desc = "Outdoor nature landscape scene featuring clear blue sky, open air, and lush green vegetation."
            matched_tags.extend(["nature", "landscape", "outdoor", "sky", "green", "trees"])
        elif vis.get("is_green"):
            desc = "Close-up nature photography with vibrant green foliage, plants, and natural outdoor setting."
            matched_tags.extend(["nature", "green", "plants", "foliage", "outdoor", "garden"])
        elif vis.get("is_warm"):
            desc = "Warm-toned photograph with golden light, autumn hues, flowers, or sunset nature colors."
            matched_tags.extend(["warm", "golden", "nature", "sunset", "autumn", "flowers", "sun"])
        elif vis.get("is_blue"):
            desc = "Scenic photograph with prominent blue tones, sky, water, or open outdoor atmosphere."
            matched_tags.extend(["blue", "sky", "water", "scenic", "outdoor"])
        else:
            clean_name = " ".join(clean_words) or "visual subject"
            desc = f"Professional photograph showcasing {clean_name} with high quality composition and balanced lighting."
            matched_tags.extend(clean_words)
        matched_descs.append(desc)

    elif not matched_descs and file_type == "video":
        clean_name = " ".join(clean_words) or "video footage"
        desc = f"Video clip recording {clean_name} with dynamic movement and high-definition visual content."
        matched_tags.extend(["video", "clip", "footage"] + clean_words)
        matched_descs.append(desc)

    elif not matched_descs and file_type == "pdf":
        if extracted_text:
            text_snippet = extracted_text[:400].replace("\n", " ").strip()
            desc = f"Document containing: {text_snippet}"
            matched_tags.extend(_extract_tags_from_text(extracted_text[:1000]))
        else:
            clean_name = " ".join(clean_words) or "document"
            desc = f"PDF document covering {clean_name} with technical information and structured content."
            matched_tags.extend(["pdf", "document", "brochure", "report"] + clean_words)
        matched_descs.append(desc)

    combined_desc = " ".join(matched_descs)
    prefix = {
        "image": "Image: ",
        "video": "Video: ",
        "pdf": "Document: ",
    }.get(file_type, "")

    final_desc = prefix + combined_desc
    # Deduplicate tags
    all_tags = list(dict.fromkeys([t.lower() for t in matched_tags if len(t) > 1]))
    return final_desc, all_tags


# Keep the text sent to the embedding model reasonably bounded.
# The complete PDF text is still stored in MongoDB.
PDF_EMBED_MAX_CHARS = 8000


def create_indexing_job(
    total_files: int,
) -> UUID:
    """
    Create a new indexing job and return its UUID.

    The job tracks overall indexing progress so that the frontend
    can later display progress such as:
        12 / 100 files processed
        10 successful
        2 failed
    """
    if total_files < 0:
        raise ValueError("total_files cannot be negative.")

    job_id = uuid4()
    now = utc_now()
    indexing_jobs_collection.insert_one(
        {
            "id": str(job_id),
            "total_files": total_files,
            "processed_files": 0,
            "successful_files": 0,
            "failed_files": 0,
            "skipped_files": 0,
            "status": "running",
            "started_at": now,
            "completed_at": None,
            "created_at": now,
        }
    )
    return job_id


def update_indexing_job(
    job_id: UUID,
    *,
    outcome: str,
) -> None:
    """
    Record the outcome of one asset in an indexing job.

    outcome must be one of:
    - success
    - failed
    - skipped

    processed_files is incremented for every completed asset attempt,
    including skipped assets.
    """
    if outcome not in {"success", "failed", "skipped"}:
        raise ValueError(
            "Invalid indexing job outcome. "
            "Expected 'success', 'failed', or 'skipped'."
        )

    increments = {
        "processed_files": 1,
        "successful_files": int(outcome == "success"),
        "failed_files": int(outcome == "failed"),
        "skipped_files": int(outcome == "skipped"),
    }
    job = indexing_jobs_collection.find_one_and_update(
        {"id": str(job_id)},
        {"$inc": increments},
        return_document=ReturnDocument.AFTER,
    )
    if job and job["processed_files"] >= job["total_files"]:
        indexing_jobs_collection.update_one(
            {"id": str(job_id)},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": utc_now(),
                }
            },
        )


def mark_asset_failed(
    asset_id: UUID,
    error_message: str,
) -> None:
    """Store a failed processing state in MongoDB."""
    assets_collection.update_one(
        {"id": str(asset_id)},
        {
            "$set": {
                "status": "failed",
                "error_message": error_message,
                "updated_at": utc_now(),
            }
        },
    )


def index_asset(
    asset_id: UUID,
    *,
    job_id: UUID | None = None,
    force: bool = False,
) -> dict:
    """
    Process one asset through:

    1. AI/content understanding
    2. Searchable text generation
    3. Embedding generation
    4. Qdrant indexing
    5. MongoDB status update
    6. Optional indexing-job progress update

    Supported asset types:
    - Images: Moondream
    - Videos: sampled frames + Moondream
    - PDFs: PyMuPDF text extraction

    PDF OCR for image-only/scanned PDFs is not implemented yet.

    job_id is optional so existing callers continue to work.
    """

    db = assets_collection

    try:
        asset = db.find_one(
            {"id": str(asset_id)},
            {
                "_id": 0,
                "id": 1,
                "filename": 1,
                "original_path": 1,
                "file_type": 1,
                "extracted_text": 1,
                "status": 1,
            },
        )

        if not asset:
            raise ValueError(
                f"Asset not found: {asset_id}"
            )

        # ---------------------------------------------------------
        # ALREADY INDEXED
        # ---------------------------------------------------------
        if asset["status"] == "indexed" and not force:

            result = {
                "status": "skipped",
                "reason": "Asset is already indexed.",
                "asset_id": str(asset_id),
                "filename": asset["filename"],
            }

            if job_id is not None:
                update_indexing_job(
                    job_id,
                    outcome="skipped",
                )

            return result

        asset_path = Path(asset["original_path"])

        # ---------------------------------------------------------
        # FILE EXISTENCE
        # ---------------------------------------------------------
        if not asset_path.exists():

            error_message = (
                f"Asset file does not exist: {asset_path}"
            )

            mark_asset_failed(asset_id, error_message)

            if job_id is not None:
                update_indexing_job(
                    job_id,
                    outcome="failed",
                )

            raise FileNotFoundError(error_message)

        db.update_one(
            {"id": str(asset_id)},
            {
                "$set": {
                    "status": "ai_processing",
                    "error_message": None,
                    "updated_at": utc_now(),
                }
            },
        )

        description = ""
        tags: list[str] = []
        extracted_text = asset.get("extracted_text")

        if asset["file_type"] == "image":
            description = generate_image_description(asset_path)
        elif asset["file_type"] == "video":
            frames = extract_video_frames(
                asset_path,
                max_frames=5,
                max_image_size=384,
            )
            description = generate_video_description(frames)
        elif asset["file_type"] == "pdf":
            if not extracted_text:
                extracted_text = extract_pdf_text(asset_path)
            if not extracted_text:
                raise ValueError("PDF contains no extractable text.")
            description = " ".join(extracted_text.split())[:PDF_EMBED_MAX_CHARS]
            tags = _extract_tags_from_text(extracted_text[:PDF_EMBED_MAX_CHARS])
        else:
            raise ValueError(f"Unsupported asset type: {asset['file_type']}")

        if asset["file_type"] in {"image", "video"}:
            tags = _extract_tags_from_text(description)

        if asset["file_type"] == "pdf":
            db.update_one(
                {"id": str(asset_id)},
                {"$set": {"extracted_text": extracted_text, "updated_at": utc_now()}},
            )

        # Only factual model output or extracted document text is searchable.
        db.update_one(
            {"id": str(asset_id)},
            {
                "$set": {
                    "description": description,
                    "tags": tags,
                    "status": "ai_processed",
                    "error_message": None,
                    "updated_at": utc_now(),
                }
            },
        )

        # ---------------------------------------------------------
        # EMBEDDING
        # ---------------------------------------------------------
        # Embed only model-grounded visual descriptions or extracted PDF text.
        embed_input = (
            extracted_text[:PDF_EMBED_MAX_CHARS]
            if asset["file_type"] == "pdf"
            else description
        )
        vector = generate_embedding(embed_input)

        # ---------------------------------------------------------
        # QDRANT
        # ---------------------------------------------------------
        upsert_asset_embedding(
            UUID(str(asset["id"])),
            vector,
            filename=asset["filename"],
            file_type=asset["file_type"],
            tags=tags,
        )

        # ---------------------------------------------------------
        # COMPLETE ASSET
        # ---------------------------------------------------------
        db.update_one(
            {"id": str(asset_id)},
            {
                "$set": {
                    "status": "indexed",
                    "tags": tags,
                    "error_message": None,
                    "updated_at": utc_now(),
                }
            },
        )

        if job_id is not None:
            update_indexing_job(
                job_id,
                outcome="success",
            )

        return {
            "status": "indexed",
            "asset_id": str(asset_id),
            "filename": asset["filename"],
            "file_type": asset["file_type"],
            "tags": tags,
        }

    except Exception as exc:
        mark_asset_failed(asset_id, str(exc))

        if job_id is not None:
            update_indexing_job(
                job_id,
                outcome="failed",
            )

        raise
