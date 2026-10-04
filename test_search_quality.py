"""
Search Quality Evaluation — NexusDAM
Tests 10 natural-language queries against the indexed asset collection.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from backend.app.services.search_service import search_assets

TESTS = [
    {
        "query": "A woman standing with a cat",
        "expect_filetype": "video",
        "expect_keywords": ["woman", "cat"],
        "description": "Should find woman+cat video",
    },
    {
        "query": "Customer testimonial videos",
        "expect_filetype": "video",
        "expect_keywords": ["testimonial", "customer"],
        "description": "Should find testimonial-named videos",
    },
    {
        "query": "Videos containing construction activity",
        "expect_filetype": "video",
        "expect_keywords": ["construction"],
        "description": "Should find construction site video",
    },
    {
        "query": "Images showing a modern living room",
        "expect_filetype": "image",
        "expect_keywords": ["living", "room", "interior", "modern"],
        "description": "Should find living room interior image",
    },
    {
        "query": "Brochures related to residential projects",
        "expect_filetype": "pdf",
        "expect_keywords": ["residential", "brochure", "project"],
        "description": "Should find residential PDF brochure",
    },
    {
        "query": "Yellow flower nature photography",
        "expect_filetype": "image",
        "expect_keywords": ["flower", "nature", "yellow"],
        "description": "Should return flower images from outdoor/nature category",
    },
    {
        "query": "Mountain landscape outdoor scenic",
        "expect_filetype": "image",
        "expect_keywords": ["mountain", "landscape", "outdoor", "scenic"],
        "description": "Should return landscape/mountain images",
    },
    {
        "query": "Aerial view of buildings and construction site",
        "expect_filetype": "image",
        "expect_keywords": ["aerial", "construction", "building"],
        "description": "Should find aerial or construction images",
    },
    {
        "query": "PDF document with technical content",
        "expect_filetype": "pdf",
        "expect_keywords": ["pdf", "document", "technical"],
        "description": "Should return PDF documents",
    },
    {
        "query": "People working outdoors workers on site",
        "expect_filetype": "image",
        "expect_keywords": ["worker", "outdoor", "people"],
        "description": "Should find workers or outdoor people images",
    },
    {
        "query": "Modern kitchen interior design",
        "expect_filetype": "image",
        "expect_keywords": ["kitchen", "interior", "modern"],
        "description": "Should find kitchen interior image",
    },
    {
        "query": "Cat portrait close-up animal",
        "expect_filetype": "image",
        "expect_keywords": ["cat", "portrait", "animal"],
        "description": "Should find cat portrait image",
    },
]

def keyword_match(result: dict, keywords: list[str]) -> bool:
    """Check if any of the expected keywords appear in filename or description."""
    blob = (
        (result.get("filename") or "").lower().replace("_", " ") + " " +
        (result.get("description") or "").lower()
    )
    return any(kw in blob for kw in keywords)

def evaluate():
    print("=" * 70)
    print("  NexusDAM — Search Quality Evaluation (10+ queries)")
    print("=" * 70)

    passed = 0
    failed = 0
    partial = 0

    for i, test in enumerate(TESTS, 1):
        query = test["query"]
        expect_ft = test.get("expect_filetype")
        expect_kw = test.get("expect_keywords", [])

        try:
            # Search with type filter if expected type is specific
            results = search_assets(query, limit=5, file_type=expect_ft)
            if not results:
                # Try without filter as fallback
                results = search_assets(query, limit=5)
        except Exception as e:
            results = []
            print(f"\n[{i:2}] QUERY: {query}")
            print(f"     ERROR: {e}")
            failed += 1
            continue

        top = results[0] if results else None
        top_score = top["score"] if top else 0.0
        top_file = top["filename"] if top else "(no results)"
        top_type = top["file_type"] if top else "—"
        top_desc = (top.get("description") or "")[:80] if top else ""

        # Evaluate relevance
        has_keyword_match = top and keyword_match(top, expect_kw)
        type_match = top and (not expect_ft or top_type == expect_ft)
        relevant = has_keyword_match and type_match
        score_ok = top_score > 0.05

        if relevant and score_ok:
            status = "PASS"
            passed += 1
        elif results and (has_keyword_match or type_match):
            status = "PARTIAL"
            partial += 1
        else:
            status = "FAIL"
            failed += 1

        print(f"\n[{i:2}] [{status}] {query}")
        print(f"     Expect: {expect_ft or 'any'} | keywords={expect_kw}")
        print(f"     Top-1 : {top_type} | score={top_score:.4f} | {top_file}")
        print(f"     Desc  : {top_desc}")
        if results:
            print(f"     All   : {', '.join(r['filename'][:30] for r in results[:3])}")

    print("\n" + "=" * 70)
    print(f"  RESULTS: {passed} PASS | {partial} PARTIAL | {failed} FAIL  (of {len(TESTS)} tests)")
    print("=" * 70)

if __name__ == "__main__":
    evaluate()
