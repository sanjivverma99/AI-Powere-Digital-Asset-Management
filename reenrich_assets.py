"""
Re-enrichment script: Assigns semantically meaningful descriptions to all assets
that have generic/poor descriptions, then re-embeds them into Qdrant.

Strategy:
- For named images (e.g. modern_living_room.jpg): generate description from filename + color analysis
- For numbered Pixabay images: use PIL image analysis (dominant colors, brightness, aspect ratio)
  to classify into visual categories (nature, architecture, people, abstract, etc.)
- For all: update DB and re-upsert Qdrant embedding
"""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from pathlib import Path
from uuid import UUID

# Force UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from backend.app.db.database import SessionLocal
from sqlalchemy import text
from backend.app.services.embedding_service import generate_embedding
from backend.app.services.qdrant_service import upsert_asset_embedding, ensure_collection

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("WARNING: Pillow not installed. Color analysis disabled.")


# ── Image Analysis Helpers ────────────────────────────────────────────────────

def get_dominant_colors(img_path: Path, n_colors: int = 5):
    """Returns top dominant RGB colors from an image using quantization."""
    try:
        img = Image.open(img_path).convert("RGB")
        img = img.resize((150, 150), Image.LANCZOS)
        quantized = img.quantize(colors=n_colors, method=Image.Quantize.FASTOCTREE)
        palette = quantized.getpalette()
        counts = {}
        pixels = list(quantized.getdata())
        for px in pixels:
            counts[px] = counts.get(px, 0) + 1
        sorted_colors = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        colors = []
        for idx, _ in sorted_colors[:n_colors]:
            r = palette[idx * 3]
            g = palette[idx * 3 + 1]
            b = palette[idx * 3 + 2]
            colors.append((r, g, b))
        return colors
    except Exception:
        return []


def classify_color(r, g, b):
    """Map RGB to a color name."""
    h_max = max(r, g, b)
    h_min = min(r, g, b)
    brightness = (r + g + b) / 3
    saturation = (h_max - h_min) / max(h_max, 1)

    if brightness < 40:
        return "black"
    if brightness > 215 and saturation < 0.15:
        return "white"
    if saturation < 0.12:
        if brightness < 100:
            return "dark gray"
        return "gray"

    # Determine hue
    if h_max == r:
        if g > b:
            return "orange" if g > r * 0.6 else "red"
        return "red" if r > 150 else "dark red"
    elif h_max == g:
        if r > b * 0.8 and r > 100:
            return "yellow-green"
        if b > r * 0.7:
            return "cyan" if b > 150 else "teal"
        return "green"
    else:  # blue dominant
        if r > g * 0.8 and r > 100:
            return "purple"
        if r > 100:
            return "blue-purple"
        return "blue" if b > 100 else "dark blue"


def analyze_image(img_path: Path) -> dict:
    """Analyze image and return visual features dict."""
    result = {
        "brightness": "medium",
        "dominant_colors": [],
        "aspect": "landscape",
        "color_names": [],
        "is_sky_blue": False,
        "has_green": False,
        "has_warm": False,
        "is_dark": False,
    }

    if not PIL_AVAILABLE:
        return result

    try:
        img = Image.open(img_path).convert("RGB")
        w, h = img.size
        result["aspect"] = "portrait" if h > w * 1.1 else ("square" if abs(h - w) < w * 0.1 else "landscape")

        # Sample brightness
        small = img.resize((50, 50))
        arr = np.array(small)
        avg_brightness = arr.mean()
        result["brightness"] = "dark" if avg_brightness < 80 else ("bright" if avg_brightness > 170 else "medium")
        result["is_dark"] = avg_brightness < 80

        colors = get_dominant_colors(img_path, n_colors=6)
        result["dominant_colors"] = colors

        color_names = [classify_color(r, g, b) for r, g, b in colors[:4]]
        result["color_names"] = color_names

        # Specific scene hints
        result["is_sky_blue"] = any(b > r and b > g and b > 120 for r, g, b in colors[:3])
        result["has_green"] = any(g > r * 1.2 and g > b * 1.1 and g > 80 for r, g, b in colors[:4])
        result["has_warm"] = any(r > g * 1.2 and r > b * 1.3 and r > 100 for r, g, b in colors[:4])

    except Exception as e:
        pass

    return result


# ── Description Generators ───────────────────────────────────────────────────

# Keyword to descriptive phrases mapping based on filename keywords
FILENAME_DESCRIPTIONS = {
    # Nature & outdoors
    "flower": "Close-up photograph of vibrant flowers in bloom, with colorful petals and lush green foliage in the background. Nature photography showcasing floral beauty.",
    "rose": "Beautiful rose flower in full bloom with rich red or pink petals. Macro photography capturing delicate floral details.",
    "sunflower": "Bright yellow sunflower with a large brown center disc, standing tall in a sunny field. Summer nature photography.",
    "tulip": "Colorful tulip flowers in bloom, showcasing spring garden beauty with vivid colors.",
    "garden": "Outdoor garden scene with flowering plants, colorful blooms, and lush green vegetation. Landscaping and horticulture photography.",
    "forest": "Woodland forest scene with tall trees, dappled sunlight filtering through leaves, and a natural pathway.",
    "tree": "Natural outdoor scene featuring tall trees with lush green canopy. Forest or park environment photography.",
    "mountain": "Dramatic mountain landscape with towering rocky peaks, possible snow coverage, and scenic panoramic views.",
    "lake": "Scenic lake landscape with calm reflective water surface, surrounded by trees or mountains.",
    "river": "Flowing river through natural landscape with banks, stones, and surrounding vegetation.",
    "beach": "Sandy beach coastal scene with ocean waves, blue water, and scenic shoreline.",
    "ocean": "Vast ocean or sea scene with waves, blue water, and coastal or horizon views.",
    "sunset": "Beautiful sunset or sunrise scene with warm orange, pink, and golden sky colors over horizon.",
    "sunrise": "Scenic sunrise photograph with warm golden tones, pink sky and sun emerging over the horizon.",
    "sky": "Scenic sky photograph with clouds, blue sky, or atmospheric conditions.",
    "cloud": "Dramatic cloudscape photograph with various cloud formations against blue or grey sky.",
    "rain": "Rainy weather scene with rain drops, wet surfaces, and overcast conditions.",
    "snow": "Winter snow scene with white snow covered ground, trees, or landscape.",
    "waterfall": "Scenic waterfall with cascading water flowing over rocks into a pool below.",
    "desert": "Arid desert landscape with sand dunes, dry terrain, and sparse vegetation.",
    "animal": "Wildlife or animal photograph showing a creature in its natural habitat.",
    "bird": "Bird photography showing a bird perched or in flight in a natural outdoor setting.",
    "cat": "Cat portrait or photograph featuring a domestic cat with distinctive fur patterns.",
    "dog": "Dog photograph showing a domestic canine, possibly playing, sitting, or running.",
    "horse": "Photograph of a horse in a field, stable, or during equestrian activity.",
    "wildlife": "Wildlife nature photography capturing animals in their natural habitat.",

    # Architecture & real estate
    "building": "Architectural photograph of a building exterior showing structural design, facade, and urban environment.",
    "house": "Residential house exterior photograph showing home architecture, garden, and property features.",
    "apartment": "Modern apartment building or residential complex with multiple floors and contemporary design.",
    "construction": "Active construction site with building materials, equipment, scaffolding, and workers in hard hats.",
    "interior": "Interior photograph showing indoor space with furniture, decor, and room layout design.",
    "living": "Living room interior photograph showing comfortable seating, decorative elements, and home decor.",
    "kitchen": "Modern kitchen interior with countertops, appliances, cabinetry, and clean contemporary design.",
    "bedroom": "Bedroom interior photograph with bed, pillows, furniture, and cozy sleeping environment.",
    "bathroom": "Bathroom interior with fixtures, tiles, modern fittings, and clean design.",
    "office": "Office workspace interior with desks, chairs, computers, and professional environment.",
    "property": "Real estate property photograph showing residential or commercial building and surroundings.",
    "estate": "Estate or property exterior photograph showing large residential or commercial property.",
    "residential": "Residential neighborhood or housing development with homes and community infrastructure.",
    "luxury": "Luxury high-end property or interior design with premium finishes and elegant decor.",
    "aerial": "Aerial or overhead photograph showing bird's eye view of buildings, landscape, or urban area.",
    "skyline": "Urban city skyline photograph showing buildings, towers, and metropolitan architecture.",
    "urban": "Urban city photography showing streets, buildings, traffic, and metropolitan environment.",
    "street": "Street level photograph of an urban road with sidewalks, buildings, and city activity.",
    "bridge": "Photograph of a bridge structure spanning over water or valley, showing engineering and architecture.",
    "architecture": "Architectural photography showcasing building design, structural details, and construction.",

    # People & lifestyle
    "woman": "Portrait or lifestyle photograph of a woman in an outdoor or indoor setting.",
    "man": "Portrait or lifestyle photograph of a man in a casual or professional setting.",
    "person": "Lifestyle photograph featuring a person engaged in activity or posing for a portrait.",
    "people": "Group of people in social or community setting, interacting or engaged in activity.",
    "family": "Family photograph showing parents and children together in a warm domestic setting.",
    "portrait": "Close-up portrait photograph of a person showing facial features and expression.",
    "outdoor": "Outdoor lifestyle photograph showing a person in a natural or urban outdoor environment.",
    "worker": "Worker or employee photograph in a professional or industrial work environment.",
    "business": "Business professional or corporate setting photograph with office environment.",
    "meeting": "Business meeting or conference room scene with professionals discussing at a table.",
    "customer": "Customer or client interaction photograph in a service or retail environment.",
    "testimonial": "Customer testimonial video or interview format with person speaking to camera.",

    # Technology & abstract
    "technology": "Technology photograph featuring digital devices, computers, or tech equipment.",
    "abstract": "Abstract artistic photograph with geometric shapes, patterns, colors, or artistic composition.",
    "texture": "Close-up texture photograph showing material surface details, patterns, or tactile qualities.",
    "pattern": "Repeating pattern photograph with geometric or organic design elements.",
    "food": "Food photography showing prepared dish, ingredients, or culinary presentation.",
    "coffee": "Coffee or beverage photograph, possibly with latte art, beans, or cafe setting.",

    # Pexels specific
    "babydov": "Outdoor lifestyle photograph featuring a person in a natural setting with vivid colors.",
    "cottonbro": "Lifestyle or studio photograph by Cottonbro Studio featuring people in an indoor setting.",
    "helenalopes": "Nature or lifestyle photograph with warm tones and natural lighting.",
    "meruyert": "Professional portrait or lifestyle photograph with cinematic composition.",
    "gonullu": "Artistic portrait or lifestyle photography with professional lighting and composition.",
}

# Scene categories for numbered images based on color analysis
def generate_pixabay_description(filename: str, analysis: dict) -> str:
    """Generate a semantic description for a numbered Pixabay image using color analysis."""
    colors = analysis["color_names"]
    brightness = analysis["brightness"]
    aspect = analysis["aspect"]
    is_sky = analysis["is_sky_blue"]
    has_green = analysis["has_green"]
    has_warm = analysis["has_warm"]
    is_dark = analysis["is_dark"]

    color_str = " and ".join(set(c for c in colors[:3] if c not in ["gray", "white", "black"]))
    if not color_str:
        color_str = colors[0] if colors else "natural"

    # Classify scene type based on visual features
    if is_sky and has_green:
        scene = "outdoor nature landscape with blue sky and green vegetation"
        keywords = "outdoor nature landscape sky green trees scenic photography"
    elif is_sky and not has_green:
        scene = "outdoor scenic photograph with clear blue sky and open environment"
        keywords = "outdoor sky scenic landscape bright daylight photography"
    elif has_green and not is_sky:
        scene = "close-up nature photograph with lush green vegetation and plant life"
        keywords = "nature green foliage plant close-up garden botanical photography"
    elif has_warm and brightness == "bright":
        scene = "warm-toned photograph with golden or orange hues, possibly sunset, flowers, or autumn scene"
        keywords = "warm orange golden nature sunset autumn flowers colorful photography"
    elif is_dark and not has_warm:
        scene = "dark atmospheric photograph with deep shadows and dramatic mood"
        keywords = "dark atmospheric dramatic moody photography night shadows"
    elif brightness == "bright" and not has_warm:
        scene = "bright well-lit photograph with clean light tones and clear subject"
        keywords = "bright clean light airy indoor portrait minimal photography"
    elif "blue" in colors or "dark blue" in colors:
        scene = "photograph with prominent blue tones, possibly water, sky, or night scene"
        keywords = "blue water ocean sea sky night photography cool tones"
    else:
        scene = f"professional stock photograph with {color_str} tones"
        keywords = f"stock photography professional {color_str} image visual content"

    format_desc = "portrait format" if aspect == "portrait" else ("square format" if aspect == "square" else "landscape format")

    return (
        f"A {brightness} {format_desc} {scene}. "
        f"Professional stock photography capturing visual subject matter. "
        f"Keywords: {keywords}."
    )


def generate_filename_description(filename: str) -> str:
    """Generate a meaningful description from a descriptive filename."""
    # Clean filename
    stem = Path(filename).stem.lower()
    stem = re.sub(r'[_\-]+', ' ', stem)
    stem = re.sub(r'\d+', '', stem).strip()
    words = stem.split()

    # Find matching keyword descriptions
    matched_desc = None
    for keyword, desc in FILENAME_DESCRIPTIONS.items():
        if keyword in words or any(keyword in w for w in words):
            matched_desc = desc
            break

    if matched_desc:
        return matched_desc

    # Fallback: construct from words
    clean_name = ' '.join(w for w in words if len(w) > 2)
    return (
        f"Professional photograph depicting {clean_name}. "
        f"Visual asset showcasing {clean_name} subject matter with high image quality."
    )


# ── Main Re-enrichment Logic ─────────────────────────────────────────────────

DATA_DIR = Path("data")

def find_file(original_path: str, filename: str) -> Path | None:
    """Find the actual file on disk."""
    # Try candidates
    candidates = [
        Path(original_path),
        DATA_DIR / Path(original_path).relative_to(Path(original_path).anchor).as_posix().lstrip('/'),
        DATA_DIR / "images" / filename,
        DATA_DIR / "videos" / filename,
        DATA_DIR / "pdfs" / filename,
    ]
    for c in candidates:
        try:
            if c.exists():
                return c
        except Exception:
            pass
    return None


def reenrich_and_reembed():
    ensure_collection()
    db = SessionLocal()

    try:
        # Get all assets that need re-enrichment
        # Either has generic description or no description at all
        rows = db.execute(text("""
            SELECT id, filename, file_type, original_path, description, status
            FROM assets
            WHERE (
                description LIKE 'Sample photograph%'
                OR description IS NULL
                OR description = ''
            )
            AND status IN ('indexed', 'failed', 'pending', 'ai_processed')
            ORDER BY file_type, filename
        """)).mappings().all()

        print(f"Found {len(rows)} assets needing re-enrichment")
        print("=" * 60)

        success = 0
        failed = 0

        for i, row in enumerate(rows):
            asset_id = str(row["id"])
            filename = row["filename"]
            file_type = row["file_type"]
            original_path = row["original_path"] or ""

            print(f"[{i+1:3}/{len(rows)}] {file_type:6} {filename[:45]}", end="", flush=True)

            try:
                # Find file on disk
                file_path = find_file(original_path, filename)

                # Generate new description
                if file_type == "image":
                    if filename.startswith("sample_pixabay_") and file_path:
                        analysis = analyze_image(file_path)
                        description = generate_pixabay_description(filename, analysis)
                    else:
                        # Named images: use filename-based generation + optional color analysis
                        description = generate_filename_description(filename)
                        if file_path and PIL_AVAILABLE:
                            analysis = analyze_image(file_path)
                            # Enrich with color info if we found keyword match
                            color_str = " and ".join(set(c for c in analysis["color_names"][:2] if c not in ["gray"]))
                            if color_str:
                                description = description.rstrip(".") + f", with dominant {color_str} tones."
                else:
                    # Skip non-images for now (videos/PDFs have real descriptions usually)
                    print(" ... SKIP (non-image)")
                    continue

                # Update description in DB
                db.execute(text("""
                    UPDATE assets
                    SET description = :description,
                        status = 'ai_processed',
                        updated_at = NOW()
                    WHERE id = :asset_id
                """), {"description": description, "asset_id": asset_id})
                db.commit()

                # Generate new embedding
                vector = generate_embedding(description)

                # Upsert into Qdrant
                upsert_asset_embedding(
                    UUID(asset_id),
                    vector,
                    filename=filename,
                    file_type=file_type,
                )

                # Mark as indexed
                db.execute(text("""
                    UPDATE assets
                    SET status = 'indexed', error_message = NULL, updated_at = NOW()
                    WHERE id = :asset_id
                """), {"asset_id": asset_id})
                db.commit()

                print(f" ... OK  [{description[:60]}]")
                success += 1

            except Exception as e:
                print(f" ... FAIL: {e}")
                failed += 1
                db.rollback()
                continue

        print("\n" + "=" * 60)
        print(f"Re-enrichment complete: {success} succeeded, {failed} failed")

    finally:
        db.close()


if __name__ == "__main__":
    reenrich_and_reembed()
