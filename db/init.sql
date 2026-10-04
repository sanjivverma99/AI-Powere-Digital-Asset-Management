-- =============================================================
-- AI-Powered Digital Asset Management  –  Database Schema
-- =============================================================
-- Executed automatically by the postgres container on first boot.
-- Idempotent: safe to re-run (CREATE IF NOT EXISTS / ON CONFLICT).
-- =============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- -------------------------------------------------------------
-- ASSETS
-- Core table: one row per unique file, keyed by original_path.
-- sha256 is used for deduplication across different folder paths.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assets (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    filename          TEXT         NOT NULL,
    original_path     TEXT         NOT NULL UNIQUE,

    file_type         VARCHAR(20)  NOT NULL,   -- image | video | pdf
    mime_type         TEXT,

    size_bytes        BIGINT       NOT NULL,
    sha256            CHAR(64)     NOT NULL,

    -- Image / video resolution
    width             INTEGER,
    height            INTEGER,

    -- Video-specific
    duration_seconds  DOUBLE PRECISION,
    frame_rate        DOUBLE PRECISION,

    -- PDF-specific
    page_count        INTEGER,

    -- AI-generated content understanding
    description       TEXT,          -- AI-generated natural-language description
    extracted_text    TEXT,          -- OCR / PDF text layer

    -- Processing pipeline state
    -- pending | scanning | ai_processing | indexed | failed | unsupported
    status            VARCHAR(30)  NOT NULL DEFAULT 'pending',
    error_message     TEXT,

    file_modified_at  TIMESTAMPTZ,

    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);


-- -------------------------------------------------------------
-- INDEXING JOBS
-- Tracks each background indexing run so the UI can poll progress.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS indexing_jobs (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    total_files       INTEGER      NOT NULL DEFAULT 0,
    processed_files   INTEGER      NOT NULL DEFAULT 0,
    successful_files  INTEGER      NOT NULL DEFAULT 0,
    failed_files      INTEGER      NOT NULL DEFAULT 0,
    skipped_files     INTEGER      NOT NULL DEFAULT 0,

    -- pending | running | completed | failed
    status            VARCHAR(30)  NOT NULL DEFAULT 'pending',

    started_at        TIMESTAMPTZ,
    completed_at      TIMESTAMPTZ,

    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);


-- -------------------------------------------------------------
-- AI TAGS
-- Denormalized AI-generated tags per asset with confidence scores.
-- Useful for filter UIs and faceted search without vector queries.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_tags (
    id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id   UUID    NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    tag        TEXT    NOT NULL,
    confidence REAL,                        -- 0.0 – 1.0
    source     VARCHAR(50) DEFAULT 'ai',    -- ai | manual
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (asset_id, tag)
);


-- -------------------------------------------------------------
-- USERS  (lightweight; no auth system required for this project)
-- Stored so the schema is complete and ready for future auth work.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email        TEXT        NOT NULL UNIQUE,
    display_name TEXT,
    role         VARCHAR(20) NOT NULL DEFAULT 'viewer',   -- viewer | admin
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- -------------------------------------------------------------
-- INDEXES
-- -------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_assets_sha256
    ON assets(sha256);

CREATE INDEX IF NOT EXISTS idx_assets_file_type
    ON assets(file_type);

CREATE INDEX IF NOT EXISTS idx_assets_status
    ON assets(status);

CREATE INDEX IF NOT EXISTS idx_assets_created_at
    ON assets(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_assets_file_modified_at
    ON assets(file_modified_at);

CREATE INDEX IF NOT EXISTS idx_ai_tags_asset_id
    ON ai_tags(asset_id);

CREATE INDEX IF NOT EXISTS idx_ai_tags_tag
    ON ai_tags(tag);


-- =============================================================
-- SEED DATA  (5 sample assets – pre-populated for demo / tests)
-- Real files are NOT required; descriptions let Qdrant index
-- them for immediate semantic-search testing.
-- ON CONFLICT DO NOTHING makes re-running this file safe.
-- =============================================================
INSERT INTO assets (
    id, filename, original_path,
    file_type, mime_type,
    size_bytes, sha256,
    width, height,
    duration_seconds, frame_rate,
    page_count,
    description, extracted_text,
    status, file_modified_at, created_at, updated_at
)
VALUES

-- 1. Image – modern living room interior
(
    'a1000000-0000-0000-0000-000000000001',
    'modern_living_room.jpg',
    '/data/images/modern_living_room.jpg',
    'image', 'image/jpeg',
    2457600,
    'aabbccddeeff00112233445566778899aabbccddeeff00112233445566778801',
    1920, 1080, NULL, NULL, NULL,
    'A bright and spacious modern living room featuring a large sectional sofa in neutral tones, a glass coffee table, and floor-to-ceiling windows letting in natural light. The walls are painted soft white with minimal artwork. A potted plant sits in the corner next to a bookshelf.',
    NULL,
    'indexed',
    NOW() - INTERVAL '10 days',
    NOW() - INTERVAL '10 days',
    NOW() - INTERVAL '10 days'
),

-- 2. Image – residential construction site
(
    'a1000000-0000-0000-0000-000000000002',
    'construction_site_overview.jpg',
    '/data/images/construction_site_overview.jpg',
    'image', 'image/jpeg',
    3145728,
    'aabbccddeeff00112233445566778899aabbccddeeff00112233445566778802',
    2560, 1440, NULL, NULL, NULL,
    'An aerial view of a large residential construction site. Several multi-story building frames are visible with scaffolding erected around them. Construction workers in hard hats and safety vests are seen operating heavy machinery including cranes and concrete mixers. Building materials such as steel beams and lumber are stacked nearby.',
    NULL,
    'indexed',
    NOW() - INTERVAL '9 days',
    NOW() - INTERVAL '9 days',
    NOW() - INTERVAL '9 days'
),

-- 3. Video – customer testimonial
(
    'a1000000-0000-0000-0000-000000000003',
    'customer_testimonial_john.mp4',
    '/data/videos/customer_testimonial_john.mp4',
    'video', 'video/mp4',
    52428800,
    'aabbccddeeff00112233445566778899aabbccddeeff00112233445566778803',
    1920, 1080, 120.0, 30.0, NULL,
    'A customer testimonial video featuring John, a homeowner, sitting in his newly renovated kitchen. He speaks directly to the camera sharing his positive experience with the residential construction company. He mentions high-quality craftsmanship, on-time delivery, and excellent communication throughout the project. Modern cabinetry and granite countertops are visible in the background.',
    NULL,
    'indexed',
    NOW() - INTERVAL '8 days',
    NOW() - INTERVAL '8 days',
    NOW() - INTERVAL '8 days'
),

-- 4. Video – woman with cat in park
(
    'a1000000-0000-0000-0000-000000000004',
    'woman_with_cat_park.mp4',
    '/data/videos/woman_with_cat_park.mp4',
    'video', 'video/mp4',
    31457280,
    'aabbccddeeff00112233445566778899aabbccddeeff00112233445566778804',
    1280, 720, 65.0, 24.0, NULL,
    'A short video clip showing a young woman standing in a sunny park holding a fluffy orange tabby cat. The woman is smiling and gently petting the cat. Trees and a walking path are visible in the background. The cat appears comfortable and calm in the woman''s arms.',
    NULL,
    'indexed',
    NOW() - INTERVAL '7 days',
    NOW() - INTERVAL '7 days',
    NOW() - INTERVAL '7 days'
),

-- 5. PDF – residential project brochure
(
    'a1000000-0000-0000-0000-000000000005',
    'residential_project_brochure_2024.pdf',
    '/data/pdfs/residential_project_brochure_2024.pdf',
    'pdf', 'application/pdf',
    5242880,
    'aabbccddeeff00112233445566778899aabbccddeeff00112233445566778805',
    NULL, NULL, NULL, NULL, 12,
    'Residential Project Brochure 2024 – Luxury Homes by GreenBuild Developers. Presents the Oakwood Residences project, a premium gated community with 3 and 4 BHK apartments. Details include floor plans, pricing starting at $450,000, project timeline, nearby infrastructure, and sustainability features such as solar panels and rainwater harvesting. Located in the northern suburbs with easy highway access.',
    'OAKWOOD RESIDENCES 2024

GreenBuild Developers proudly presents Oakwood Residences, a premier gated residential community offering luxurious 3 BHK and 4 BHK apartments.

Project Highlights:
- 250 units across 5 towers
- Prices starting from $450,000
- Expected completion: Q4 2025
- RERA registered

Amenities: Swimming pool, clubhouse, gymnasium, children''s play area, 24/7 security, landscaped gardens.

Location: Northern Suburbs, direct access to Highway 7, 8 km from city centre.

Sustainability: Solar rooftop panels, rainwater harvesting, EV charging stations.

Floor Plans:
3 BHK – 1,450 sq ft to 1,650 sq ft
4 BHK – 2,100 sq ft to 2,400 sq ft

Contact: sales@greenbuild.example.com',
    'indexed',
    NOW() - INTERVAL '6 days',
    NOW() - INTERVAL '6 days',
    NOW() - INTERVAL '6 days'
)

ON CONFLICT (original_path) DO NOTHING;


-- -------------------------------------------------------------
-- SEED – AI TAGS for demo assets
-- -------------------------------------------------------------
INSERT INTO ai_tags (asset_id, tag, confidence, source)
VALUES
    ('a1000000-0000-0000-0000-000000000001', 'living room',    0.97, 'ai'),
    ('a1000000-0000-0000-0000-000000000001', 'interior',       0.95, 'ai'),
    ('a1000000-0000-0000-0000-000000000001', 'modern',         0.93, 'ai'),
    ('a1000000-0000-0000-0000-000000000001', 'sofa',           0.91, 'ai'),
    ('a1000000-0000-0000-0000-000000000001', 'natural light',  0.88, 'ai'),

    ('a1000000-0000-0000-0000-000000000002', 'construction',   0.98, 'ai'),
    ('a1000000-0000-0000-0000-000000000002', 'building site',  0.96, 'ai'),
    ('a1000000-0000-0000-0000-000000000002', 'workers',        0.92, 'ai'),
    ('a1000000-0000-0000-0000-000000000002', 'crane',          0.89, 'ai'),
    ('a1000000-0000-0000-0000-000000000002', 'residential',    0.85, 'ai'),

    ('a1000000-0000-0000-0000-000000000003', 'testimonial',    0.99, 'ai'),
    ('a1000000-0000-0000-0000-000000000003', 'customer',       0.97, 'ai'),
    ('a1000000-0000-0000-0000-000000000003', 'kitchen',        0.90, 'ai'),
    ('a1000000-0000-0000-0000-000000000003', 'renovation',     0.88, 'ai'),
    ('a1000000-0000-0000-0000-000000000003', 'homeowner',      0.86, 'ai'),

    ('a1000000-0000-0000-0000-000000000004', 'woman',          0.97, 'ai'),
    ('a1000000-0000-0000-0000-000000000004', 'cat',            0.99, 'ai'),
    ('a1000000-0000-0000-0000-000000000004', 'park',           0.93, 'ai'),
    ('a1000000-0000-0000-0000-000000000004', 'outdoor',        0.90, 'ai'),
    ('a1000000-0000-0000-0000-000000000004', 'pet',            0.88, 'ai'),

    ('a1000000-0000-0000-0000-000000000005', 'brochure',       0.99, 'ai'),
    ('a1000000-0000-0000-0000-000000000005', 'residential',    0.97, 'ai'),
    ('a1000000-0000-0000-0000-000000000005', 'real estate',    0.95, 'ai'),
    ('a1000000-0000-0000-0000-000000000005', 'luxury homes',   0.91, 'ai'),
    ('a1000000-0000-0000-0000-000000000005', 'floor plans',    0.88, 'ai')

ON CONFLICT (asset_id, tag) DO NOTHING;


-- -------------------------------------------------------------
-- SEED – Demo users
-- -------------------------------------------------------------
INSERT INTO users (id, email, display_name, role)
VALUES
    ('b1000000-0000-0000-0000-000000000001', 'admin@dam.local',  'System Admin',  'admin'),
    ('b1000000-0000-0000-0000-000000000002', 'viewer@dam.local', 'Demo Viewer',   'viewer')
ON CONFLICT (email) DO NOTHING;