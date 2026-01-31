# Auction Sheet OCR System — Combined Implementation Plan

> Internal web app for processing USS auction sheet images with PaddleOCR, enabling search, review, and export of extracted vehicle data.
> 
> **Updated based on analysis of 10 actual auction sheet images**

---

## Executive Summary

| Aspect | Decision |
|--------|----------|
| **Scale** | ~10s of documents/day, single-digit auction sources |
| **Languages** | Japanese + English (bilingual search) |
| **WhatsApp** | Yes — MVP can start with a team-managed number; plan to migrate to a business-managed account |
| **Compliance** | Standard practices (no special requirements) |
| **Source Format** | USS auction system (WhatsApp screenshots) |
| **Expected Auto-pass Rate** | ~80%+ once quality gates are defined (field-level confidence + validation rules + regression-tested) |
| **Quality Gate** | Golden set + field-level targets + auto-pass policy + regression suite on every pipeline/model change |

**Timeline estimate:** 10-11 weeks to production-ready

---

## Table of Contents

1. [Key Findings from Image Analysis](#1-key-findings-from-image-analysis)
2. [Architecture Overview](#2-architecture-overview)
3. [Tech Stack](#3-tech-stack)
4. [Database Schema](#4-database-schema)
5. [OCR Pipeline](#5-ocr-pipeline)
6. [Extraction Strategy](#6-extraction-strategy)
7. [API Specification](#7-api-specification)
8. [UI Specification](#8-ui-specification)
9. [WhatsApp Integration](#9-whatsapp-integration)
10. [Deployment](#10-deployment)
11. [Milestone Plan](#11-milestone-plan)
12. [Appendix: Code Scaffolds](#12-appendix-code-scaffolds)

---

## 1. Key Findings from Image Analysis

### Image Characteristics

| Aspect | Observation | Impact |
|--------|-------------|--------|
| **Source** | All are WhatsApp screenshots of USS auction system | Consistent format = template approach viable |
| **Layout** | Two-column: auction sheet (left ~60%) + vehicle photos (right ~40%) | Can crop out photos to reduce noise |
| **Header** | Blue table with key data: lot, venue, date, model, mileage, price, score | **High-value region** — very structured |
| **Main Sheet** | Japanese form with handwritten + printed text | More OCR challenges here |
| **Resolution** | ~900x650px, JPEG compression artifacts | May need upscaling for small text |
| **Venues** | 東京 (Tokyo), 名古屋 (Nagoya), 大阪 (Osaka) | Multiple auction houses |

### Data Structure Identified

**From the Blue Header Table (most reliable source):**

| Field | Japanese | Example Values | Reliability |
|-------|----------|----------------|-------------|
| 開催日 | Auction date | 24/10/17, 24/10/18 | ⭐⭐⭐⭐⭐ |
| 会場 | Venue | 東京, 名古屋, 大阪 | ⭐⭐⭐⭐⭐ |
| 出品番号 | Lot number | 75241, 73547, 25888 | ⭐⭐⭐⭐⭐ |
| 車種名/グレード | Model/Grade | ポル タイカン GTS, MB CLA250 | ⭐⭐⭐⭐ |
| 年式 | Year | R05, R03, R02 (Reiwa era) | ⭐⭐⭐⭐⭐ |
| シフト/排気量 | Trans/Engine | AT, FA, CA / 2000, 2400, 2500 | ⭐⭐⭐⭐ |
| 走行 | Mileage | 8, 4, 15 (×1000km likely) | ⭐⭐⭐⭐ |
| 車検 | Inspection | R08.09, R08.03 | ⭐⭐⭐⭐ |
| 色 | Color | ホワイト, グレー, パール | ⭐⭐⭐⭐ |
| 型式 | Model code | J1NE, 118347M, TALA15 | ⭐⭐⭐⭐⭐ |
| セリ結果 | Result | ● 落札 (sold) | ⭐⭐⭐⭐⭐ |
| 応札額/スタート金額 | Bid/Start price | 9,115 / 7,480 | ⭐⭐⭐⭐⭐ |
| 評価点 | Score | 4.5, 5, R | ⭐⭐⭐⭐⭐ |

**From the Left Auction Sheet:**

| Field | Notes | Reliability |
|-------|-------|-------------|
| 車台 No. | Chassis/VIN | ⭐⭐⭐⭐ (printed) |
| 走行 km | Detailed mileage | ⭐⭐⭐ (handwritten) |
| 注意事項 | Notes/warnings | ⭐⭐⭐ (mixed) |
| 検査員報告 | Inspector report | ⭐⭐ (handwritten) |
| Damage diagram | Car outline with marks | ⭐⭐ (needs special handling) |

### Key Recommendation: Prioritize the Blue Header Table

This is your **golden data source**. It's:
- Digitally rendered (not handwritten)
- Highly structured (table format)
- Contains all critical fields
- Consistent across all images

**Recommendation:** Extract header table first, treat auction sheet as supplementary.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                  CLIENTS                                     │
│                                                                             │
│    ┌──────────────┐         ┌──────────────┐         ┌──────────────┐      │
│    │   Web App    │         │  Mobile Web  │         │   WhatsApp   │      │
│    │  (Next.js)   │         │  (responsive)│         │   Business   │      │
│    └──────┬───────┘         └──────┬───────┘         └──────┬───────┘      │
└───────────┼────────────────────────┼────────────────────────┼──────────────┘
            │                        │                        │
            └────────────────────────┼────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               API GATEWAY                                    │
│                                                                             │
│                         ┌──────────────────┐                                │
│                         │    FastAPI       │                                │
│                         │    Backend       │                                │
│                         └────────┬─────────┘                                │
│                                  │                                          │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
            ▼                      ▼                      ▼
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
│    PostgreSQL     │  │      Redis        │  │    MinIO/S3       │
│    (data store)   │  │   (queue/cache)   │  │  (file storage)   │
└───────────────────┘  └─────────┬─────────┘  └───────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            WORKER POOL                                       │
│                                                                             │
│    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                   │
│    │ Preprocess  │───▶│  OCR (GPU)  │───▶│  Extract    │                   │
│    │   Worker    │    │   Worker    │    │   Worker    │                   │
│    └─────────────┘    └─────────────┘    └─────────────┘                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Service Responsibilities

| Service | Role | Scaling |
|---------|------|---------|
| **Web App** | UI, auth, user interactions | Horizontal (but 1 instance fine for your scale) |
| **FastAPI Backend** | REST API, job orchestration, webhooks | Single instance sufficient |
| **Celery Workers** | Async OCR processing | 1 GPU worker + 1-2 CPU workers |
| **PostgreSQL** | Source of truth, full-text search | Single instance + daily backups |
| **Redis** | Task queue, session cache | Single instance |
| **MinIO/S3** | Image storage, OCR artifacts | Single bucket with prefixes |

---

## 3. Tech Stack

### Frontend

| Category | Choice | Rationale |
|----------|--------|-----------|
| **Framework** | Next.js 14 (App Router) | SSR for SEO-irrelevant but good DX, API routes for BFF pattern |
| **Styling** | Tailwind CSS + shadcn/ui | Clean ops UI, no design system fights |
| **State** | TanStack Query v5 | Polling job status, cache invalidation, optimistic updates |
| **Forms** | React Hook Form + Zod | Type-safe validation, keyboard-friendly for review queue |
| **Tables** | TanStack Table | Virtualization, column customization |
| **Image Viewer** | OpenSeadragon | Deep zoom for auction sheets, annotation overlays |
| **Icons** | Lucide React | Consistent, tree-shakeable |

### Backend

| Category | Choice | Rationale |
|----------|--------|-----------|
| **Framework** | FastAPI | Async, Pydantic validation, OpenAPI docs free |
| **Task Queue** | Celery + Redis | Task chaining, retries, Flower monitoring |
| **ORM** | SQLAlchemy 2.0 | Async support, mature |
| **Migrations** | Alembic | Standard for SQLAlchemy |
| **Auth** | FastAPI-Users + JWT | Simple, supports OAuth if needed later |
| **File Handling** | boto3 (S3-compatible) | Works with MinIO locally, AWS S3 in prod |

### OCR & ML (Updated Based on Image Analysis)

| Model | Use For | Why |
|-------|---------|-----|
| **PaddleOCR v4** (not VL) | Header table | Better for structured Japanese text |
| **PaddleOCR-VL-1.5** | Auction sheet | Better for document understanding |
| **Tesseract 5 + jpn** | Fallback | Free, handles kana well |

**Why not VL for everything?** 
VL excels at document-level understanding but the header table is a simple structured grid—standard OCR with table detection is faster and more accurate here.

| Category | Choice | Rationale |
|----------|--------|-----------|
| **Image Processing** | OpenCV + Pillow | Preprocessing, crop extraction |
| **Layout Detection** | PaddleX Layout / PPStructure | Table detection for header |

### Infrastructure

| Category | Choice | Rationale |
|----------|--------|-----------|
| **Containerization** | Docker + Docker Compose | Local dev parity, simple deployment |
| **Object Storage** | MinIO (dev) / S3 (prod) | S3-compatible, free locally |
| **Monitoring** | Flower + basic logging | Sufficient for your scale |
| **Reverse Proxy** | Caddy or nginx | Auto HTTPS with Caddy |

---

## 4. Database Schema

### ERD Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌────────────────────┐
│     users       │     │   documents     │     │   auction_records   │
├─────────────────┤     ├─────────────────┤     ├────────────────────┤
│ id (PK)         │     │ id (PK)         │◄────│ id (PK)             │
│ email           │◄────│ uploaded_by(FK) │     │ document_id(FK)     │
│ hashed_password │     │ source          │     │ lot_no              │
│ role            │     │ status          │     │ make_model          │
│ created_at      │     │ original_path   │     │ mileage_km          │
│ updated_at      │     │ hash_sha256     │     │ score               │
└─────────────────┘     │ roi (JSONB)     │     │ evidence (JSONB)    │
                        └─────────────────┘     │ fts_vector_en       │
                                                │ search_text         │
                                                └──────────┬─────────┘
                                                           │
                                                           ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │    overrides    │     │  whatsapp_meta  │
                        ├─────────────────┤     ├─────────────────┤
                        │ id (PK)         │     │ id (PK)         │
                        │ record_id (FK)  │     │ document_id (FK)│
                        │ field_name      │     │ message_id      │
                        │ old_value       │     │ from_number     │
                        │ new_value       │     │ received_at     │
                        │ user_id (FK)    │     └─────────────────┘
                        │ created_at      │
                        └─────────────────┘
```

### Full DDL

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy search

-- Keep updated_at in sync if you rely on it for UI ordering / audit views.
-- (Alternative: do this in app code; triggers avoid accidental drift.)
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'staff',  -- admin, ops_lead, staff, viewer
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- Documents table (one per uploaded image)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Source tracking
    source VARCHAR(50) NOT NULL DEFAULT 'upload',  -- upload, whatsapp
    uploaded_by UUID REFERENCES users(id),
    
    -- Processing status
    status VARCHAR(50) NOT NULL DEFAULT 'queued',  -- queued, preprocessing, ocr, extracting, done, failed, review
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- File references
    original_path VARCHAR(500) NOT NULL,
    thumb_path VARCHAR(500),
    preprocessed_path VARCHAR(500),

    -- ROI detection results (stored to make reprocessing deterministic)
    -- Example: {"header_bbox":[x0,y0,x1,y1], "sheet_bbox":[...], "photos_bbox":[...], "roi_version":"v1"}
    roi JSONB,

    -- Deduplication
    hash_sha256 VARCHAR(64) NOT NULL UNIQUE,
    
    -- Pipeline versioning
    model_version VARCHAR(50),
    pipeline_version VARCHAR(50),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_documents_status ON documents(status);
-- hash_sha256 is UNIQUE, so it is already indexed implicitly
CREATE INDEX idx_documents_created ON documents(created_at DESC);
CREATE INDEX idx_documents_source ON documents(source);

CREATE TRIGGER trg_documents_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

    -- Auction records table (extracted data)
    CREATE TABLE auction_records (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        
        -- Core fields (typed for filtering)
        auction_date DATE,
        auction_venue VARCHAR(255),
        auction_venue_round VARCHAR(50),       -- e.g., "1488回"
        lot_no VARCHAR(100),
        
        -- Vehicle info
        make VARCHAR(100),
        model VARCHAR(255),
        make_model VARCHAR(255),  -- Combined for easier search
        grade VARCHAR(100),
        model_code VARCHAR(100),               -- 型式 (e.g., "TALA15", "J1NE")
        chassis_no VARCHAR(100),               -- 車台No / VIN (often from the sheet)
        year INTEGER,
    
    -- Japanese era year (for reference)
    model_year_reiwa VARCHAR(10),         -- 'R05'
    model_year_gregorian INTEGER,          -- 2023
    
    -- Inspection expiry (often provided as year-month, e.g. R08.09)
    inspection_expiry_raw TEXT,
    inspection_expiry_month DATE,          -- stored as first day of the month for filtering/sorting
    
    -- Engine/transmission
    engine_cc INTEGER,                     -- 2000, 2400, 2500
    transmission VARCHAR(20),              -- AT, FA, CA, CVT
    -- Condition
    mileage_km INTEGER,

    -- Mileage transparency (header may be abbreviated; keep inference metadata)
    mileage_raw TEXT,                       -- raw token as seen (e.g., "8" or "8.1" or "81,000")
    mileage_multiplier INTEGER,             -- 1 or 1000
    mileage_inference_conf DECIMAL(3,2),    -- 0.00..1.00

    score VARCHAR(20),                      -- "4.5", "R", "***", etc.
    score_numeric DECIMAL(3,1),             -- parsed numeric for filtering
    color VARCHAR(100),

    -- Auction result (canonical in JPY)
    result VARCHAR(50),                     -- sold, unsold, negotiating
    starting_bid_yen INTEGER,
    final_bid_yen INTEGER,

    -- Convenience derived columns (optional; avoid dual sources of truth)
    starting_bid_man INTEGER GENERATED ALWAYS AS (starting_bid_yen / 10000) STORED,
    final_bid_man INTEGER GENERATED ALWAYS AS (final_bid_yen / 10000) STORED,

    -- USS-specific

    lane_type VARCHAR(50),                 -- プライムコーナー, Aコーナー, etc.
    equipment_codes TEXT,                  -- AAC, ナビ, SR, AW, 革, PS, PW
    
    -- Normalized model info (bilingual)
    make_ja VARCHAR(100),                  -- トヨタ
    make_en VARCHAR(100),                  -- Toyota
    model_ja VARCHAR(100),                 -- ハリアー
    model_en VARCHAR(100),                 -- Harrier
    
    -- Inspector findings (structured)
    inspector_notes JSONB,                 -- {"interior": "汚れ", "wheels": "キズ", ...}
    damage_locations JSONB,                -- [{"panel": "front_bumper", "type": "A1"}, ...]
    
    -- Raw text
    notes_text TEXT,
    options_text TEXT,
    full_text TEXT,  -- All OCR text concatenated
    
    -- Extraction evidence (JSONB for flexibility)
    -- Structure: {"field_name": {"value": "...", "confidence": 0.95, "bbox": [x,y,w,h], "crop_path": "...", "source": "header|sheet"}}
    evidence JSONB DEFAULT '{}',
    
    -- Review status
    needs_review BOOLEAN DEFAULT false,
    review_reason TEXT,
    is_verified BOOLEAN DEFAULT false,
    verified_by UUID REFERENCES users(id),
    verified_at TIMESTAMP WITH TIME ZONE,
    
    -- Confidence scores
    overall_confidence DECIMAL(3,2),
    
    -- Search support
    -- Postgres built-in FTS doesn't segment Japanese well, so use:
    -- - fts_vector_en: English/Latin FTS + ranking
    -- - search_text: JP/EN substring + fuzzy matching (ILIKE / similarity) via pg_trgm
        fts_vector_en tsvector GENERATED ALWAYS AS (
        to_tsvector('english',
        COALESCE(lot_no, '') || ' ' ||
        COALESCE(auction_venue, '') || ' ' ||
        COALESCE(auction_venue_round, '') || ' ' ||
        COALESCE(make_model, '') || ' ' ||
        COALESCE(model_code, '') || ' ' ||
        COALESCE(chassis_no, '') || ' ' ||
        COALESCE(notes_text, '') || ' ' ||
        COALESCE(options_text, '') || ' ' ||
        COALESCE(full_text, '')
        )
        ) STORED,

        search_text TEXT GENERATED ALWAYS AS (
        COALESCE(lot_no, '') || ' ' ||
        COALESCE(auction_venue, '') || ' ' ||
        COALESCE(auction_venue_round, '') || ' ' ||
        COALESCE(make_model, '') || ' ' ||
        COALESCE(make_ja, '') || ' ' ||
        COALESCE(make_en, '') || ' ' ||
        COALESCE(model_ja, '') || ' ' ||
        COALESCE(model_en, '') || ' ' ||
        COALESCE(model_code, '') || ' ' ||
        COALESCE(chassis_no, '') || ' ' ||
        COALESCE(notes_text, '') || ' ' ||
        COALESCE(options_text, '') || ' ' ||
        COALESCE(full_text, '')
        ) STORED,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

    -- Indexes for common queries
    CREATE INDEX idx_records_document ON auction_records(document_id);
    CREATE INDEX idx_records_auction_date ON auction_records(auction_date DESC);
    CREATE INDEX idx_records_auction_venue ON auction_records(auction_venue);
    CREATE INDEX idx_records_lot ON auction_records(lot_no);
    CREATE INDEX idx_records_make_model ON auction_records(make_model);
    CREATE INDEX idx_records_model_code ON auction_records(model_code);
    CREATE INDEX idx_records_chassis_no ON auction_records(chassis_no);
    CREATE INDEX idx_records_mileage ON auction_records(mileage_km);
    CREATE INDEX idx_records_score ON auction_records(score_numeric);
    CREATE INDEX idx_records_price ON auction_records(final_bid_yen);
    CREATE INDEX idx_records_needs_review ON auction_records(needs_review) WHERE needs_review = true;
    CREATE INDEX idx_records_fts_en ON auction_records USING GIN(fts_vector_en);

    -- Trigram indexes for fuzzy search
    CREATE INDEX idx_records_make_model_trgm ON auction_records USING GIN(make_model gin_trgm_ops);
    CREATE INDEX idx_records_model_code_trgm ON auction_records USING GIN(model_code gin_trgm_ops);
    CREATE INDEX idx_records_chassis_no_trgm ON auction_records USING GIN(chassis_no gin_trgm_ops);
    CREATE INDEX idx_records_search_text_trgm ON auction_records USING GIN(search_text gin_trgm_ops);

-- GIN index on evidence JSONB
CREATE INDEX idx_records_evidence ON auction_records USING GIN(evidence);

-- Equipment/options lookup
CREATE TABLE equipment_codes (
    code VARCHAR(20) PRIMARY KEY,
    name_ja VARCHAR(100),
    name_en VARCHAR(100),
    category VARCHAR(50)
);

INSERT INTO equipment_codes VALUES
    ('AAC', 'オートエアコン', 'Auto A/C', 'comfort'),
    ('ナビ', 'カーナビ', 'Navigation', 'electronics'),
    ('SR', 'サンルーフ', 'Sunroof', 'exterior'),
    ('AW', 'アルミホイール', 'Alloy Wheels', 'exterior'),
    ('革', '革シート', 'Leather Seats', 'interior'),
    ('PS', 'パワーステアリング', 'Power Steering', 'mechanical'),
    ('PW', 'パワーウィンドウ', 'Power Windows', 'comfort'),
    ('DR', 'ドライブレコーダー', 'Dash Cam', 'electronics');

-- Overrides table (audit trail for human corrections)
CREATE TABLE overrides (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    record_id UUID NOT NULL REFERENCES auction_records(id) ON DELETE CASCADE,
    field_name VARCHAR(100) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    reason TEXT,
    user_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_overrides_record ON overrides(record_id);
CREATE INDEX idx_overrides_user ON overrides(user_id);

-- WhatsApp metadata (optional module)
CREATE TABLE whatsapp_meta (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- Filled once a Document is created for this message; nullable so we can claim idempotency
    -- before downloading media / creating the document.
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    message_id VARCHAR(255) NOT NULL UNIQUE,
    from_number VARCHAR(50) NOT NULL,
    chat_id VARCHAR(255),
    received_at TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'received',  -- received, queued, rejected, processed, failed
    error_message TEXT,
    raw_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_whatsapp_document ON whatsapp_meta(document_id);
CREATE INDEX idx_whatsapp_status ON whatsapp_meta(status);
-- message_id is UNIQUE, so it is already indexed implicitly

CREATE TRIGGER trg_whatsapp_meta_updated_at
BEFORE UPDATE ON whatsapp_meta
FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- Extraction templates (config-driven extraction)
CREATE TABLE extraction_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    regions JSONB NOT NULL,
    fields JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TRIGGER trg_extraction_templates_updated_at
BEFORE UPDATE ON extraction_templates
FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_auction_records_updated_at
BEFORE UPDATE ON auction_records
FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- Useful views
CREATE VIEW review_queue AS
SELECT 
    ar.*,
    d.original_path,
    d.thumb_path,
    d.source
FROM auction_records ar
JOIN documents d ON ar.document_id = d.id
WHERE ar.needs_review = true
ORDER BY ar.created_at DESC;

CREATE VIEW recent_records AS
SELECT 
    ar.*,
    d.original_path,
    d.thumb_path,
    d.source,
    d.status as document_status
FROM auction_records ar
JOIN documents d ON ar.document_id = d.id
ORDER BY ar.created_at DESC
LIMIT 100;
```

---

## 5. OCR Pipeline

### Pipeline Stages

```
┌─────────┐    ┌─────────────┐    ┌─────────┐    ┌───────────┐    ┌──────────┐
│ Upload  │───▶│ Preprocess  │───▶│   OCR   │───▶│  Extract  │───▶│ Validate │
└─────────┘    └─────────────┘    └─────────┘    └───────────┘    └──────────┘
     │               │                 │               │                │
     ▼               ▼                 ▼               ▼                ▼
 [queued]     [preprocessing]       [ocr]       [extracting]    [done/review]
```

### Stage Details

#### 5.1 Upload & Preflight

```python
def handle_upload(file, user_id, source='upload'):
    # 1) Read bytes once (hash + upload + thumbnail)
    file_bytes = file.read()
    file_hash = sha256(file_bytes).hexdigest()
    
    # 2) Optional pre-check for duplicate (fast path)
    existing = db.query(Document).filter_by(hash_sha256=file_hash).first()
    if existing:
        return {"status": "duplicate", "existing_id": existing.id}
    
    # 3) Store original
    original_path = storage.upload_bytes(f"originals/{uuid4()}.{ext}", file_bytes)
    
    # 4) Create thumbnail
    thumb_bytes = create_thumbnail_bytes(file_bytes, max_size=400)
    thumb_path = storage.upload_bytes(f"thumbs/{uuid4()}.jpg", thumb_bytes)
    
    # 5) Create document record
    doc = Document(
        source=source,
        uploaded_by=user_id,
        status='queued',
        original_path=original_path,
        thumb_path=thumb_path,
        hash_sha256=file_hash
    )
    db.add(doc)
    try:
        db.commit()
    except IntegrityError:
        # Enforces dedup under concurrent uploads (hash_sha256 is UNIQUE).
        db.rollback()
        existing = db.query(Document).filter_by(hash_sha256=file_hash).first()
        return {"status": "duplicate", "existing_id": existing.id}
    
    # 6. Enqueue processing
    celery.send_task('preprocess', args=[doc.id])
    
    return {"status": "queued", "document_id": doc.id}
```

#### 5.2 Preprocessing (Updated for USS Images)

```python
@celery.task(bind=True, max_retries=3)
def preprocess(self, document_id):
    doc = db.get(Document, document_id)
    doc.status = 'preprocessing'
    doc.processing_started_at = datetime.utcnow()
    db.commit()
    
    try:
        # Download + decode original
        image_bytes = storage.download(doc.original_path)
        image = decode_image(image_bytes)  # np.ndarray (BGR)
        
        # USS-specific preprocessing
        image = preprocess_auction_image(image)

        # Detect + persist ROIs (header/sheet/photos) for deterministic reprocessing/debugging
        rois = detect_rois(image)
        doc.roi = {
            "header_bbox": list(rois.header_bbox),
            "sheet_bbox": list(rois.sheet_bbox),
            "photos_bbox": list(rois.photos_bbox) if rois.photos_bbox else None,
            "roi_version": "v1",
        }
        
        # Save preprocessed
        preprocessed_bytes = encode_png(image)
        preprocessed_path = storage.upload(
            f"preprocessed/{document_id}.png", 
            preprocessed_bytes
        )
        doc.preprocessed_path = preprocessed_path
        db.commit()
        
        # Chain to OCR
        ocr.delay(document_id)
        
    except Exception as e:
        doc.status = 'failed'
        doc.error_message = str(e)
        db.commit()
        raise self.retry(exc=e, countdown=60)


def preprocess_auction_image(image):
    """Optimized for USS WhatsApp screenshots with JPEG artifacts.

    `image` is expected to be an OpenCV BGR np.ndarray.
    """
    h, w = image.shape[:2]
    
    # 1. Upscale for small text (header has ~12px font)
    if h < 1000:
        scale = 1500 / h
        image = cv2.resize(image, None, fx=scale, fy=scale, 
                          interpolation=cv2.INTER_CUBIC)
    
    # 2. Denoise JPEG artifacts
    image = cv2.fastNlMeansDenoisingColored(image, h=6, hForColorComponents=6)
    
    # 3. Sharpen for text clarity
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    image = cv2.filter2D(image, -1, kernel)
    
    # 4. Increase contrast in header region (blue background)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    l = clahe.apply(l)
    image = cv2.merge([l, a, b])
    image = cv2.cvtColor(image, cv2.COLOR_LAB2BGR)
    
    return image
```

#### 5.3 Two-Pass OCR Processing

```python
@celery.task(bind=True, max_retries=2)
def ocr(self, document_id):
    doc = db.get(Document, document_id)
    doc.status = 'ocr'
    db.commit()
    
    try:
        image_bytes = storage.download(doc.preprocessed_path)
        image = decode_image(image_bytes)  # np.ndarray (BGR)
        
        # Prefer persisted ROIs for deterministic crops; fallback to re-detection.
        rois = None
        if doc.roi and doc.roi.get("roi_version") == "v1":
            rois = RoiResult(
                header_bbox=tuple(doc.roi["header_bbox"]),
                sheet_bbox=tuple(doc.roi["sheet_bbox"]),
                photos_bbox=tuple(doc.roi["photos_bbox"]) if doc.roi.get("photos_bbox") else None,
            )
        
        # Pass 1: Header table (high confidence)
        header_data = extract_header_table(image, rois=rois)
        
        # Pass 2: Auction sheet (supplementary)
        sheet_data = extract_auction_sheet(image, header_data, rois=rois)

        # Store raw OCR output
        ocr_results = {
            'header': header_data,
            'sheet': sheet_data
        }
        storage.upload(
            f"ocr_raw/{document_id}.json",
            json.dumps(ocr_results)
        )
        
        # Chain to extraction
        extract.delay(document_id, ocr_results)
        
    except Exception as e:
        doc.status = 'failed'
        doc.error_message = str(e)
        db.commit()
        raise self.retry(exc=e, countdown=120)
```

---

## 6. Extraction Strategy

### Region Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         BLUE HEADER TABLE                               │
│  (Primary extraction zone - detected dynamically)                              │
├────────────────────────────────────┬────────────────────────────────────┤
│                                    │                                    │
│     AUCTION SHEET                  │     VEHICLE PHOTOS                 │
│     (Secondary extraction)         │     (IGNORE - no OCR value)        │
│                                    │                                    │
│     • Corner banner (lane type)    │                                    │
│     • Lot number (redundant)       │                                    │
│     • Chassis number               │                                    │
│     • Mileage (handwritten)        │                                    │
│     • Notes section                │                                    │
│     • Inspector report             │                                    │
│     • Damage diagram               │                                    │
│                                    │                                    │
└────────────────────────────────────┴────────────────────────────────────┘
```

### Crop Configuration (Robust ROI Detection)

Avoid hard-coded pixel crops. WhatsApp screenshots vary by device, scaling, and compression. Use **detected regions of interest (ROIs)** with a **safe fallback**.

**What to store per document (recommended):**
- `header_bbox`: `[x0, y0, x1, y1]`
- `sheet_bbox`: `[x0, y0, x1, y1]`
- `photos_bbox` (optional, for debugging): `[x0, y0, x1, y1]`

These make re-processing deterministic and let you debug drift.

```python
from dataclasses import dataclass
from typing import Optional, Tuple

BBox = Tuple[int, int, int, int]  # (x0, y0, x1, y1)

@dataclass(frozen=True)
class RoiResult:
    header_bbox: BBox
    sheet_bbox: BBox
    photos_bbox: Optional[BBox] = None

def detect_rois(image) -> RoiResult:
    # Strategy (in order):
    # 1) Detect the blue header band by color (HSV threshold) + largest top rectangle.
    # 2) Detect the sheet/photo vertical split via edge density / vertical projection.
    # 3) Fallback to percent-based crops if detection fails.
    h, w = image.shape[:2]

    # --- (1) Header: detect blue band near the top ---
    header_bbox = detect_blue_header_bbox(image)
    if header_bbox is None:
        # Fallback: top ~15% (covers typical header heights across devices)
        header_bbox = (0, 0, w, int(0.15 * h))

    _, hy0, _, hy1 = header_bbox

    # --- (2) Vertical split: detect sheet vs photos ---
    split_x = detect_vertical_split_x(image, y0=hy1, y1=h)
    if split_x is None:
        # Fallback: left ~60% (empirically close to USS WhatsApp screenshots)
        split_x = int(0.60 * w)

    sheet_bbox = (0, hy1, split_x, h)
    photos_bbox = (split_x, hy1, w, h)

    return RoiResult(header_bbox=header_bbox, sheet_bbox=sheet_bbox, photos_bbox=photos_bbox)
```

**Notes**
- `detect_blue_header_bbox()` can be implemented with HSV thresholding + contour detection.
- `detect_vertical_split_x()` can use edge detection + vertical projection to find the strongest vertical boundary.
- Keep a per-source “calibration override” (UI toggle) if you later ingest non-USS sources.


### Phase 1: Header Table Extraction (High Priority)

```python
def extract_header_table(image, *, rois=None):
    """Extract structured data from the blue header table (most reliable region)."""

    rois = rois or detect_rois(image)
    x0, y0, x1, y1 = rois.header_bbox

    # 1) Crop header ROI (detected, not fixed pixels)
    header = image[y0:y1, x0:x1]

    # 2) Preprocess tuned for blue background + small text
    header = enhance_header_image(header)

    # 3) Table structure recognition
    from paddleocr import PPStructure
    table_engine = PPStructure(table=True, lang="japan")
    result = table_engine(header)

    # 4) Parse table cells into structured data
    cells = parse_table_cells(result)

    # 5) Normalize & validate (store raw alongside normalized)
    mileage_raw = cells.get("走行")
    mileage_value, mileage_multiplier, mileage_conf = parse_mileage_header(mileage_raw)
    inspection_raw = cells.get("車検")
    inspection_expiry_month = parse_reiwa_year_month(inspection_raw)

    return {
        "auction_date": parse_auction_date(cells.get("開催日")),
        "auction_venue": cells.get("会場"),
        "auction_venue_round": cells.get("開催回"),
        "lot_no": normalize_lot_no(cells.get("出品番号")),
        "model_name": cells.get("車種名"),
        "grade": cells.get("グレード"),
        "model_code": cells.get("型式"),
        "model_year": parse_reiwa_year(cells.get("年式")),
        "transmission": cells.get("シフト"),
        "engine_cc": parse_int(cells.get("排気量")),
        "mileage_raw": mileage_raw,
        "mileage_value": mileage_value,                 # numeric part
        "mileage_multiplier": mileage_multiplier,       # 1 or 1000 (inferred)
        "mileage_inference_conf": mileage_conf,         # 0..1
        "inspection_expiry_raw": inspection_raw,
        "inspection_expiry_month": inspection_expiry_month,
        "color": cells.get("色"),
        "score_raw": cells.get("評価点"),
        "score": parse_score(cells.get("評価点")),
        "starting_bid_yen": parse_yen(cells.get("スタート")),
        "final_bid_yen": parse_yen(cells.get("落札")),
        "_source": "header_table",
    }
```

**Mileage note**
The header sometimes shows abbreviated mileage (e.g., “走行 8” meaning 8,000 km). Treat this as an **inference**:
- store `mileage_raw` exactly as read
- store `mileage_multiplier` + `mileage_inference_conf`
- validate against sheet mileage when available


### Phase 2: Auction Sheet Extraction (Secondary)

```python
def extract_auction_sheet(image, header_data, *, rois=None):
    """Extract supplementary data from the main auction sheet area."""

    rois = rois or detect_rois(image)
    x0, y0, x1, y1 = rois.sheet_bbox

    # 1) Crop auction sheet ROI (detected)
    sheet = image[y0:y1, x0:x1]

    # 2) Run document OCR
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(lang="japan", use_angle_cls=True)
    result = ocr.ocr(sheet)

    # 3) Extract specific fields
    text_lines = [line[1][0] for line in result[0]]
    full_text = "\n".join(text_lines)

    data = {
        "chassis_no": extract_chassis_number(text_lines),
        "mileage_sheet": extract_mileage(text_lines),
        "recycle_fee": extract_recycle_fee(text_lines),
        "notes": extract_notes_section(text_lines),
        "inspector_report": extract_inspector_report(text_lines),
        "lane_type": extract_lane_type(sheet),  # Corner banner
        "full_text": full_text,
    }

    # 4) Cross-validate mileage (treat header units as inference)
    if data.get("mileage_sheet") and header_data.get("mileage_value"):
        header_mileage = header_data["mileage_value"] * (header_data.get("mileage_multiplier") or 1)

        # Flag if they differ materially (tunable threshold)
        if abs(header_mileage - data["mileage_sheet"]) > 1000:
            data["_mileage_discrepancy"] = True
            data["_mileage_discrepancy_detail"] = {
                "header_mileage_km": header_mileage,
                "sheet_mileage_km": data["mileage_sheet"],
                "header_raw": header_data.get("mileage_raw"),
                "header_inference_conf": header_data.get("mileage_inference_conf"),
            }

    return data
```


### Field Priority

| Priority | Field | Source | Auto-pass if confident? |
|----------|-------|--------|------------------------|
| P0 | Lot number | Header | Yes |
| P0 | Score | Header | Yes |
| P0 | Final bid | Header | Yes |
| P0 | Auction date | Header | Yes |
| P1 | Model/Grade | Header | Yes |
| P1 | Mileage | Header (validate with sheet) | Yes if match |
| P1 | Model code (型式) | Header | Yes |
| P2 | Chassis number | Sheet | No (review) |
| P2 | Color | Header | Yes |
| P3 | Notes | Sheet | No (informational) |
| P3 | Inspector report | Sheet | No (informational) |

### Japanese Era Date Handling

The USS header mixes multiple date formats:
- `開催日` (auction date): typically `YY/MM/DD` (e.g., `24/10/17` → 2024-10-17)
- `年式` (model year): **Reiwa era** shorthand (e.g., `R05` → 2023)
- `車検` (inspection expiry): usually Reiwa **year-month** (e.g., `R08.09` → 2026-09). Day is not provided, so store as month precision.

```python
def parse_reiwa_year(text: str) -> Optional[int]:
    """R05 -> 2023 (Reiwa year 1 started in 2019)."""
    if not text:
        return None
    m = re.search(r'R?(\d{1,2})', text)
    if not m:
        return None
    return int(m.group(1)) + 2018


def parse_reiwa_year_month(text: str) -> Optional[date]:
    """R08.09 -> 2026-09-01 (month precision; keep raw separately)."""
    if not text:
        return None
    m = re.search(r'R?(\d{1,2})[年/.-](\d{1,2})', text)
    if not m:
        return None
    year = int(m.group(1)) + 2018
    month = int(m.group(2))
    return date(year, month, 1)
```

### Score Handling

```python
SCORE_MAPPING = {
    '5': 5.0,
    '4.5': 4.5,
    '4': 4.0,
    '3.5': 3.5,
    '3': 3.0,
    'R': -1,      # R = Repaired/Accident history
    'RA': -1,     # Repaired Grade A
    '***': None,  # Unknown/Not graded
    '0': 0,       # Scrap
}
```

### Model Name Normalization

```python
MAKE_ALIASES = {
    'ポル': 'Porsche',
    'ポルシェ': 'Porsche',
    'MB': 'Mercedes-Benz',
    'メルセデス': 'Mercedes-Benz',
    'ベンツ': 'Mercedes-Benz',
    'BMW': 'BMW',
    'レクサス': 'Lexus',
    'トヨタ': 'Toyota',
    # ... etc
}

MODEL_ALIASES = {
    'タイカン': 'Taycan',
    'CLAクラス': 'CLA-Class',
    'ランドクルーザ': 'Land Cruiser',
    'ハリアー': 'Harrier',
    'アルファード': 'Alphard',
    # ... etc
}
```

### Lane Type Detection

```python
LANE_TEMPLATES = {
    'prime': 'プライムコーナー',      # Premium imports
    'a_corner': 'Aコーナー',           # General
    'f_prime': 'Fプライム',            # First Prime
    'golden': 'ゴールデンコーナー',    # Golden
    'import_prime': '輸入車プライムコーナー',  # Import Premium
}

def detect_lane_type(sheet_image):
    """Detect auction lane from corner banner"""
    # Banner is typically top-left of auction sheet
    h, w = sheet_image.shape[:2]
    banner_region = sheet_image[0:int(0.10 * h), 0:int(0.50 * w)]
    # OCR or template match
    # ...
```

### Extraction Regex Patterns

```python
EXTRACTION_PATTERNS = {
    # Header table patterns (for fallback if table detection fails)
    'lot_no': r'(\d{4,6})',  # 5-digit lot numbers
    'auction_date': r'(\d{2}/\d{2}/\d{2})',  # 24/10/17 format
    'auction_venue': r'(東京|名古屋|大阪|横浜|神戸|福岡)',
    'auction_venue_round': r'(\d{3,4}回)',  # 1488回, 2057回
    'model_year': r'R(\d{2})',  # R05, R03
    'score': r'評価点[:\s]*([0-9.]+|R|RA|\*+)',
    'mileage_header_raw': r'走行[:\s]*([0-9]{1,5})',  # Raw numeric token; unit multiplier inferred later
    
    # Auction sheet patterns
    'chassis_no': r'(?:車台|車体)[:\s]*([A-Z0-9-]{10,20})',
    'mileage_sheet': r'走行[:\s]*([0-9,]+)\s*(?:km|㎞)',
    'recycle_fee': r'リサイクル[:\s]*([0-9,]+)\s*円',
    'inspector_header': r'◎?検査員報告',
    
    # Equipment parsing
    'equipment': r'(AAC|ナビ|SR|AW|革|PS|PW|DR)',
}
```

### Confidence Model

| Source | Expected Accuracy | Auto-pass Threshold |
|--------|-------------------|---------------------|
| Header table (digital) | 95-99% | 90% |
| Sheet - printed text | 85-95% | 85% |
| Sheet - handwritten | 60-80% | Never auto-pass |
| Sheet - inspector report | 50-70% | Never auto-pass |

### Evaluation & Quality Gates (Make Auto-pass Real)

Define “auto-pass” with concrete, testable rules—otherwise the system will drift silently as you tweak preprocessing or OCR models.

**Golden set**
- Start with the 10 images you already analyzed; expand to 50–100 representative screenshots.
- Label only P0/P1 fields first (lot no, date, venue, score, final bid, model, mileage). Add P2+ later.

**Field-level targets (suggested initial SLOs)**
- Lot number, venue, auction date: **≥ 99% exact match**
- Score, final bid: **≥ 98–99% exact match**
- Model name/grade: **≥ 97–98% exact match**
- Mileage (normalized km): **≥ 98% within ±1,000 km** (and discrepancy flag accuracy)

**Auto-pass policy**
- P0 fields present and meet confidence thresholds (per-field, not just a single `_confidence`)
- Validation checks pass (e.g., mileage discrepancy not flagged, dates parse cleanly)
- OCR/model/pipeline version is covered by the regression suite

**Regression suite**
- Run on every change to `pipeline_version` or `model_version`
- Fail the build if field-level targets regress beyond a set tolerance

**Operational metric**
- Track review rate + reasons (missing P0, low confidence, discrepancy flags). This is the fastest signal of drift.

### Validation & Routing Logic

```python
def determine_review_needed(header_data, sheet_data, evidence):
    """Decide if human review is needed using field-level confidence + validation rules."""

    def conf(field: str) -> float:
        return float((evidence.get(field) or {}).get("confidence") or 0.0)

    # P0 fields must be present + confident
    required_p0 = ["lot_no", "auction_date", "auction_venue", "score", "final_bid_yen"]
    if not all(header_data.get(f) for f in required_p0):
        missing = [f for f in required_p0 if not header_data.get(f)]
        return True, f"Missing P0 from header: {', '.join(missing)}"

    if any(conf(f) < 0.90 for f in required_p0):
        low = [f for f in required_p0 if conf(f) < 0.90]
        return True, f"Low confidence P0: {', '.join(low)}"

    # Validation checks
    if sheet_data.get("_mileage_discrepancy"):
        return True, "Mileage mismatch between header and sheet"

    return False, None
```

---

## 7. API Specification

### Base URL

```
Production: https://api.yourcompany.com/v1
Development: http://localhost:8000/v1
```

### Authentication

JWT tokens via `Authorization: Bearer <token>` header.

### Endpoints

#### Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Get JWT token |
| POST | `/auth/refresh` | Refresh token |
| GET | `/auth/me` | Current user info |

#### Documents

| Method | Path | Description |
|--------|------|-------------|
| POST | `/documents/upload` | Upload image(s) |
| GET | `/documents` | List documents |
| GET | `/documents/{id}` | Get document details |
| GET | `/documents/{id}/status` | Get processing status |
| POST | `/documents/{id}/reprocess` | Rerun OCR (admin) |

#### Records

| Method | Path | Description |
|--------|------|-------------|
| GET | `/records` | Search/list records |
| GET | `/records/{id}` | Get record details |
| PATCH | `/records/{id}` | Update record fields |
| POST | `/records/{id}/verify` | Mark as verified |
| GET | `/records/{id}/evidence/{field}` | Get field evidence |

#### Review Queue

| Method | Path | Description |
|--------|------|-------------|
| GET | `/review` | Get review queue |
| POST | `/review/{id}/approve` | Approve with edits |
| POST | `/review/{id}/reject` | Reject document |

#### Exports

| Method | Path | Description |
|--------|------|-------------|
| POST | `/exports` | Create export job |
| GET | `/exports/{id}` | Get export status/download |

#### Webhooks (WhatsApp)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/webhooks/whatsapp` | Verification |
| POST | `/webhooks/whatsapp` | Incoming messages |

### Request/Response Examples

#### Upload

```bash
POST /v1/documents/upload
Content-Type: multipart/form-data

# Form fields:
# - files: File[] (multiple images)
# - source: string (optional, default "upload")
```

```json
// Response
{
  "documents": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "queued",
      "original_path": "originals/550e8400.jpg",
      "thumb_url": "https://storage.../thumbs/550e8400.jpg"
    }
  ],
  "duplicates": [
    {
      "filename": "image2.jpg",
      "existing_id": "660e8400-e29b-41d4-a716-446655440001"
    }
  ]
}
```

#### Search Records

```bash
GET /v1/records?q=taycan+タイカン&mileage_max=50000&score_min=4&page=1&per_page=20
```

**Search behavior (JP/EN)**
- `q` is treated as a raw query string (not pre-tokenized by the client).
- Backend combines:
  - English/Latin full-text search (`fts_vector_en`) for ranking
  - JP/EN trigram search on `search_text` for substring/fuzzy matching (works for Japanese without requiring a tokenizer extension)
  - Exact/fast-path matching when `q` looks like a lot number, model code, or chassis number

```json
// Response
{
  "items": [
    {
      "id": "...",
      "document_id": "...",
      "lot_no": "75241",
      "make_model": "Porsche Taycan GTS",
      "make_ja": "ポルシェ",
      "model_ja": "タイカン",
      "mileage_km": 8000,
      "score": "4.5",
      "final_bid_yen": 91150000,
      "auction_date": "2024-10-17",
      "overall_confidence": 0.95,
      "needs_review": false,
      "thumb_url": "https://...",
      "created_at": "2024-10-17T10:30:00Z"
    }
  ],
  "total": 156,
  "page": 1,
  "per_page": 20,
  "pages": 8
}
```

---

## 8. UI Specification

### 8.1 Global Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [Logo]    🔍 Search records...                    [Upload] [👤 User ▼] │
├────────────┬────────────────────────────────────────────────────────────┤
│            │                                                            │
│  Dashboard │                                                            │
│  Records   │                      MAIN CONTENT                          │
│  Review    │                                                            │
│  Uploads   │                                                            │
│  Exports   │                                                            │
│  ───────── │                                                            │
│  Settings  │                                                            │
│            │                                                            │
└────────────┴────────────────────────────────────────────────────────────┘
```

### 8.2 Record Detail: Show Both Sources

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Lot 75241 - Porsche Taycan GTS                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────┐  ┌─────────────────────────────────────┐  │
│  │  FROM HEADER (✓ High)   │  │  FROM SHEET (⚠ Medium)              │  │
│  ├─────────────────────────┤  ├─────────────────────────────────────┤  │
│  │  Date: 2024-10-17       │  │  Chassis: WF0ZZZY1ZPSA              │  │
│  │  Venue: Tokyo (1488回)  │  │  Mileage: 7,496 km                  │  │
│  │  Score: 4.5             │  │  Notes:                              │  │
│  │  Mileage: 8,000 km *    │  │    ・プライバシーガラス             │  │
│  │  Final: ¥91,150,000     │  │    ・レッドキャリパー              │  │
│  │  Model: ZAA-J1NE        │  │    ・ドラレコ                       │  │
│  │  Equipment: AAC SR AW   │  │  Inspector:                         │  │
│  │             革 PS PW DR │  │    大きなケーブル                   │  │
│  └─────────────────────────┘  └─────────────────────────────────────┘  │
│                                                                         │
│  * Mileage discrepancy: Header shows 8 (×1000), sheet shows 7,496     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.3 Search: Japanese + English

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🔍  [taycan OR タイカン OR ポルシェ]                        [Filters] │
├─────────────────────────────────────────────────────────────────────────┤
│  Search matches both English and Japanese terms                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.4 Quick Filters: Based on Real Data

```
┌──────────────────────┐
│ Quick Filters        │
├──────────────────────┤
│ Venue                │
│ [x] 東京 (Tokyo)     │
│ [x] 名古屋 (Nagoya)  │
│ [x] 大阪 (Osaka)     │
│                      │
│ Score                │
│ [5] [4.5] [4] [R]    │
│                      │
│ Make                 │
│ [Toyota] [Lexus]     │
│ [Porsche] [BMW]      │
│ [Mercedes] [Other]   │
│                      │
│ Price Range          │
│ ¥___万 to ¥___万     │
└──────────────────────┘
```

### 8.5 Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Dashboard                                                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │     12      │ │      3      │ │      1      │ │    8.2s     │       │
│  │  Processed  │ │  In Review  │ │   Failed    │ │  Avg Time   │       │
│  │   Today     │ │             │ │             │ │             │       │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘       │
│                                                                         │
│  Quick Actions                                                          │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐        │
│  │  📤 Upload       │ │  📋 Review Queue │ │  📊 Export       │        │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘        │
│                                                                         │
│  Recent Records                                        [View all →]     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 10:30  75241  Porsche Taycan  8,000km  4.5  ¥9,115万  ✅        │   │
│  │ 10:28  73547  Toyota Harrier  32,000km  4.0  ¥680万   ✅        │   │
│  │ 10:25  25888  Nissan Note     ------    ---  -------  ⚠️ Review │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.6 Review Queue

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Review Queue                                           3 items pending │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ ┌───────┐  25888                              ⚠️ Missing: score │   │
│  │ │ thumb │  Nissan Note                                          │   │
│  │ │       │  Oct 18, 2024                       [Review →]        │   │
│  │ └───────┘                                                        │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ ┌───────┐  34521                  ⚠️ Mileage discrepancy        │   │
│  │ │ thumb │  Mazda CX-5               Header: 15k, Sheet: 14,235  │   │
│  │ │       │  Oct 17, 2024                       [Review →]        │   │
│  │ └───────┘                                                        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Keyboard: [Tab] Next field  [Enter] Save & Next  [Esc] Skip           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 9. WhatsApp Integration

### Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   WhatsApp   │────▶│   360dialog  │────▶│  Your API    │
│    User      │     │   (or Meta)  │     │  /webhooks   │
└──────────────┘     └──────────────┘     └──────────────┘
                                                 │
                                                 ▼
                                          ┌──────────────┐
                                          │ Media        │
                                          │ Download     │
                                          └──────┬───────┘
                                                 │
                                                 ▼
                                          ┌──────────────┐
                                          │ OCR Pipeline │
                                          │ (same as     │
                                          │  upload)     │
                                          └──────────────┘
```

### Webhook Handler (Secure + Idempotent)

Key improvements over the MVP sketch:
- **Webhook signature verification** (reject spoofed requests)
- **DB-backed sender allowlist** (not a hard-coded list)
- **Idempotency** using WhatsApp `message.id` enforced in the DB (`UNIQUE(message_id)` + insert-with-conflict handling)
- **Rate limiting** + media size limits (basic abuse protection)

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, Query
from datetime import datetime
import hmac
import hashlib

router = APIRouter()

def verify_whatsapp_signature(raw_body: bytes, signature_header: str, app_secret: str) -> bool:
    # WhatsApp/Meta webhooks typically use an HMAC signature header (e.g., X-Hub-Signature-256).
    # Exact header name/provider may vary (Cloud API vs 360dialog), so keep this pluggable.
    if not signature_header:
        return False

    # Expected format: "sha256=<hex>"
    try:
        algo, sig_hex = signature_header.split("=", 1)
        if algo.lower() != "sha256":
            return False
        expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig_hex)
    except Exception:
        return False


@router.get("/webhooks/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    # Meta/360dialog webhook verification handshake
    if hub_mode == "subscribe" and hub_verify_token == settings.WA_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403)


@router.post("/webhooks/whatsapp")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()

    # 1) Verify signature (provider-specific header name)
    sig = request.headers.get("X-Hub-Signature-256") or request.headers.get("x-hub-signature-256")
    if not verify_whatsapp_signature(raw_body, sig, settings.WA_APP_SECRET):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    payload = await request.json()

    for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") != "messages":
                    continue

                value = change.get("value", {})
                for message in value.get("messages", []):
                    from_number = message.get("from")
                    message_id = message.get("id")
                    
                    # 2) Idempotency: claim message_id at the DB layer (safe under retries/concurrency)
                    claimed = await db.try_claim_whatsapp_message(
                        message_id=message_id,
                        from_number=from_number,
                        chat_id=value.get("metadata", {}).get("phone_number_id"),
                        received_at=datetime.utcnow(),
                        raw_payload=payload,
                    )
                    if not claimed:
                        continue

                    # 3) Sender allowlist (DB-backed)
                    if not await db.is_sender_allowed(from_number):
                        await send_reply(from_number, "Sorry, you're not authorized to submit images.")
                        await db.update_whatsapp_message(message_id, status="rejected", error_message="unauthorized")
                        continue

                    # 4) Only accept images
                    if message.get("type") != "image":
                        await send_reply(from_number, "Please send an image of the auction sheet.")
                        await db.update_whatsapp_message(message_id, status="rejected", error_message="not_image")
                        continue

                image_info = message.get("image", {})
                media_id = image_info.get("id")

                # 5) Enqueue durable work (prefer Celery/RQ over in-process background tasks)
                    background_tasks.add_task(
                        enqueue_whatsapp_ingest,
                        media_id=media_id,
                        from_number=from_number,
                        message_id=message_id,
                        timestamp=message.get("timestamp"),
                    )

                    await db.update_whatsapp_message(message_id, status="queued")
                    await send_reply(from_number, "📥 Image received! Processing...")

    return {"status": "ok"}
```


### Reply Templates

```python
REPLIES = {
    "received": "📥 Image received! Processing...",
    "done": "✅ Processed!\nLot: {lot_no}\nModel: {make_model}\nScore: {score}\nPrice: ¥{price}万\nView: {url}",
    "review": "⚠️ Processed but needs review.\nMissing: {missing}\nView: {url}",
    "failed": "❌ Processing failed. Please try again or upload via web.",
    "duplicate": "ℹ️ This image was already processed.\nView: {url}",
    "unauthorized": "Sorry, you're not authorized to submit images.",
    "not_image": "Please send an image of the auction sheet.",
}
```

---

## 10. Deployment

### Development (Docker Compose)

```yaml
version: '3.8'

services:
  web:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - api

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/auction_ocr
      - REDIS_URL=redis://redis:6379/0
      - S3_ENDPOINT=http://minio:9000
      - S3_ACCESS_KEY=minioadmin
      - S3_SECRET_KEY=minioadmin
      - S3_BUCKET=auction-ocr
    depends_on:
      - db
      - redis
      - minio

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/auction_ocr
      - REDIS_URL=redis://redis:6379/0
      - S3_ENDPOINT=http://minio:9000
      - S3_ACCESS_KEY=minioadmin
      - S3_SECRET_KEY=minioadmin
      - S3_BUCKET=auction-ocr
    depends_on:
      - db
      - redis
      - minio
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  flower:
    image: mher/flower:0.9.7
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - redis

  db:
    image: postgres:15
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=auction_ocr
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  minio_data:
```

### Production Deployment (AWS)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              INTERNET                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │  Cloudflare CDN  │
                          │  (optional)      │
                          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │   Caddy / nginx  │
                          │   (TLS, routing) │
                          └────────┬─────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
           ┌──────────────┐              ┌──────────────┐
           │   Next.js    │              │   FastAPI    │
           │   (SSR)      │              │   (API)      │
           └──────────────┘              └──────┬───────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
           ┌──────────────┐            ┌──────────────┐            ┌──────────────┐
           │  PostgreSQL  │            │    Redis     │            │   AWS S3     │
           │   (RDS)      │            │ (Elasticache)│            │              │
           └──────────────┘            └──────────────┘            └──────────────┘
                                                │
                                                ▼
                                       ┌──────────────┐
                                       │ GPU Worker   │
                                       │ (EC2 g4dn)   │
                                       └──────────────┘
```

**Recommended AWS Setup (for your scale):**

| Component | AWS Service | Size | Cost/month |
|-----------|-------------|------|------------|
| API + Web | EC2 t3.medium | 2 vCPU, 4GB | ~$30 |
| Worker | EC2 g4dn.xlarge | 4 vCPU, 16GB, T4 GPU | ~$150 (spot: ~$50) |
| Database | RDS db.t3.micro | 1 vCPU, 1GB | ~$15 |
| Redis | Elasticache t3.micro | 1 vCPU, 0.5GB | ~$12 |
| Storage | S3 | Pay per use | ~$5 |
| **Total** | | | **~$110-210/month** |

---

## 11. Milestone Plan

### Revised Timeline (Front-loading Header Extraction)

Given the consistent USS format, we recommend **front-loading the header extraction** for faster value delivery.

### Week 1-2: Header Table Only (MVP)

- [ ] Project setup (monorepo, Docker Compose)
- [ ] Database schema + migrations
- [ ] Create golden set + baseline field-level metrics
- [ ] Basic FastAPI with auth
- [ ] Upload endpoint + S3 storage
- [ ] Detect header ROI (blue band) + store `header_bbox` (fallback to % crop)
- [ ] PaddleOCR table extraction on header
- [ ] Parse all header fields with Japanese date handling
- [ ] Store in DB with high confidence
- [ ] Basic list view with header data

**Deliverable:** Upload → See lot, model, score, price in list (no sheet data yet)

### Week 3-4: Auction Sheet + Validation

- [ ] Detect sheet/photo split + OCR the `sheet_bbox` ROI (fallback to % crop)
- [ ] Extract chassis, detailed mileage, notes
- [ ] Infer mileage multiplier + cross-validate mileage (header vs sheet) with discrepancy policy
- [ ] Review queue for discrepancies
- [ ] Evidence storage (JSONB)
- [ ] Confidence scoring
- [ ] Record detail page with dual-source display

**Deliverable:** Full extraction with confidence indicators and discrepancy detection

### Week 5-6: Search & Filter

- [ ] Search (English FTS + JP/EN trigram search on `search_text`)
- [ ] Filter sidebar (date, mileage, score, price, venue)
- [ ] Make/model normalization dictionary
- [ ] Pagination
- [ ] Export to CSV

**Deliverable:** Searchable database with exports

### Week 7: Review Queue

- [ ] Review queue page
- [ ] Fast correction UI with image viewer
- [ ] Override recording (audit trail)
- [ ] Keyboard shortcuts
- [ ] "Verify" workflow

**Deliverable:** Human-in-the-loop review system

### Week 8-9: Hardening & Ops

- [ ] Idempotency + retry logic + dead letter queue (safe reprocessing)
- [ ] Error handling + user feedback
- [ ] Duplicate detection improvements
- [ ] Dashboard with metrics
- [ ] Config-driven extraction rules + regression suite gating
- [ ] Basic monitoring (Flower, logs)

**Deliverable:** Production-ready system

### Week 10-11: WhatsApp Integration

- [ ] 360dialog account setup
- [ ] Webhook endpoint + signature verification
- [ ] Media download pipeline
- [ ] DB-backed sender allowlist + rate limiting
- [ ] Reply messages with extracted data
- [ ] Source tagging in UI

**Deliverable:** WhatsApp image submission working

### Timeline Summary

```
Week  1  2  3  4  5  6  7  8  9  10  11
      ├──────────┼─────────┼────────┼──────┤
      │ Header   │ Search  │ Harden │  WA  │
      │   MVP    │ Review  │  Ops   │      │
      │+Sheet    │         │        │      │
```

---

## 12. Appendix: Code Scaffolds

### Project Structure

```
auction-ocr/
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── README.md
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   │
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx              # Dashboard
│   │   │   ├── records/
│   │   │   │   ├── page.tsx          # Records list
│   │   │   │   └── [id]/page.tsx     # Record detail
│   │   │   ├── review/
│   │   │   │   └── page.tsx
│   │   │   ├── upload/
│   │   │   │   └── page.tsx
│   │   │   └── exports/
│   │   │       └── page.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                   # shadcn components
│   │   │   ├── ImageViewer.tsx
│   │   │   ├── RecordTable.tsx
│   │   │   ├── FilterDrawer.tsx
│   │   │   ├── EvidencePopover.tsx
│   │   │   ├── DualSourceDisplay.tsx # Header vs Sheet data
│   │   │   └── UploadDropzone.tsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── useRecords.ts
│   │   │   ├── useUpload.ts
│   │   │   └── useJobStatus.ts
│   │   │
│   │   └── lib/
│   │       ├── api.ts
│   │       └── utils.ts
│   │
│   └── public/
│
├── backend/
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   ├── requirements.txt
│   ├── alembic.ini
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app
│   │   ├── config.py                 # Settings
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py               # Dependencies
│   │   │   ├── auth.py
│   │   │   ├── documents.py
│   │   │   ├── records.py
│   │   │   ├── review.py
│   │   │   ├── exports.py
│   │   │   └── webhooks.py
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── document.py
│   │   │   ├── record.py
│   │   │   └── whatsapp.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── document.py
│   │   │   ├── record.py
│   │   │   └── export.py
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── storage.py            # S3 operations
│   │   │   ├── search.py             # FTS queries
│   │   │   ├── normalization.py      # Make/model aliases
│   │   │   └── export.py             # CSV/XLSX generation
│   │   │
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── session.py
│   │       └── base.py
│   │
│   ├── worker/
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── preprocess.py
│   │   │   ├── ocr.py
│   │   │   ├── extract.py
│   │   │   └── validate.py
│   │   │
│   │   └── ocr/
│   │       ├── __init__.py
│   │       ├── paddle_ocr.py         # PaddleOCR wrapper
│   │       ├── preprocessing.py      # Image processing
│   │       ├── header_extraction.py  # Header table OCR
│   │       ├── sheet_extraction.py   # Auction sheet OCR
│   │       ├── date_parsing.py       # Reiwa era handling
│   │       └── normalization.py      # Make/model aliases
│   │
│   ├── migrations/
│   │   └── versions/
│   │
│   └── tests/
│
└── config/
    ├── extraction_config.yaml
    ├── make_aliases.yaml             # Japanese → English make names
    ├── model_aliases.yaml            # Japanese → English model names
    └── templates/
        └── uss.yaml
```

### Key Code Samples

#### FastAPI Main

```python
# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, documents, records, review, exports, webhooks
from app.config import settings

app = FastAPI(
    title="Auction OCR API",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
app.include_router(documents.router, prefix="/v1/documents", tags=["documents"])
app.include_router(records.router, prefix="/v1/records", tags=["records"])
app.include_router(review.router, prefix="/v1/review", tags=["review"])
app.include_router(exports.router, prefix="/v1/exports", tags=["exports"])
app.include_router(webhooks.router, prefix="/v1/webhooks", tags=["webhooks"])


@app.get("/health")
async def health():
    return {"status": "healthy"}
```

#### React Query Hook (with bilingual search)

```typescript
// frontend/src/hooks/useRecords.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

interface RecordFilters {
  q?: string;  // Supports both Japanese and English
  auction_date_from?: string;
  auction_date_to?: string;
  mileage_min?: number;
  mileage_max?: number;
  score_min?: number;
  auction_venue?: string[];  // 東京, 名古屋, 大阪
  source?: 'upload' | 'whatsapp';
  page?: number;
  per_page?: number;
}

export function useRecords(filters: RecordFilters) {
  return useQuery({
    queryKey: ['records', filters],
    queryFn: () => api.get('/records', { params: filters }),
    staleTime: 30_000,
  });
}

export function useRecord(id: string) {
  return useQuery({
    queryKey: ['record', id],
    queryFn: () => api.get(`/records/${id}`),
    enabled: !!id,
  });
}

export function useUpdateRecord() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Record> }) =>
      api.patch(`/records/${id}`, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['record', id] });
      queryClient.invalidateQueries({ queryKey: ['records'] });
    },
  });
}

export function useJobStatus(documentId: string) {
  return useQuery({
    queryKey: ['job-status', documentId],
    queryFn: () => api.get(`/documents/${documentId}/status`),
    refetchInterval: (data) => 
      data?.status === 'done' || data?.status === 'failed' ? false : 2000,
    enabled: !!documentId,
  });
}
```

---

## Summary of Changes from Original to Updated Plan

| Original Plan | Updated Based on Images |
|---------------|-------------------------|
| Generic auction sheets | Specific to USS format |
| Single OCR pass | Two-pass: header (high priority) + sheet |
| Heuristic crops | ROI detection + percent fallback; persist ROIs per document |
| Regex-heavy extraction | Table detection for header |
| Review all low confidence | Auto-pass if header complete |
| Generic date handling | Reiwa era conversion |
| English-only search | Bilingual JP/EN search (English FTS + JP/EN trigram search) |
| ~50% auto-pass expected | ~80%+ auto-pass expected (header is clean) |

The consistent USS format is a **major advantage**—you can achieve much higher automation than a generic solution.

---

## Next Steps

1. **Set up development environment**
   - Clone repo scaffold
   - Run `docker-compose up`
   - Verify all services healthy

2. **Test PaddleOCR table detection** on the header region

3. **Build chassis number regex** from more samples

4. **Create make/model normalization dictionary**

5. **Configure 360dialog** (for WhatsApp)
   - Create account
   - Get phone number verified
   - Set webhook URL

6. **Start Week 1: Header Table MVP**
   - Focus on header extraction first
   - Don't optimize sheet extraction until header pipeline works

---

*Document version: 2.0 (Combined)*  
*Last updated: January 2026*
