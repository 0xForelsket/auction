"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-01-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255)),
        sa.Column("role", sa.String(length=50), nullable=False, server_default=sa.text("'staff'")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_users_email", "users", ["email"])

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("source", sa.String(length=50), nullable=False, server_default=sa.text("'upload'")),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("error_message", sa.Text()),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("original_path", sa.String(length=500), nullable=False),
        sa.Column("thumb_path", sa.String(length=500)),
        sa.Column("preprocessed_path", sa.String(length=500)),
        sa.Column("roi", postgresql.JSONB()),
        sa.Column("hash_sha256", sa.String(length=64), nullable=False, unique=True),
        sa.Column("model_version", sa.String(length=50)),
        sa.Column("pipeline_version", sa.String(length=50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("processing_started_at", sa.DateTime(timezone=True)),
        sa.Column("processing_completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_documents_status", "documents", ["status"])
    op.create_index("idx_documents_created", "documents", [sa.text("created_at DESC")])
    op.create_index("idx_documents_source", "documents", ["source"])

    op.create_table(
        "auction_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("auction_date", sa.Date()),
        sa.Column("auction_venue", sa.String(length=255)),
        sa.Column("auction_venue_round", sa.String(length=50)),
        sa.Column("lot_no", sa.String(length=100)),
        sa.Column("make", sa.String(length=100)),
        sa.Column("model", sa.String(length=255)),
        sa.Column("make_model", sa.String(length=255)),
        sa.Column("grade", sa.String(length=100)),
        sa.Column("model_code", sa.String(length=100)),
        sa.Column("chassis_no", sa.String(length=100)),
        sa.Column("year", sa.Integer()),
        sa.Column("model_year_reiwa", sa.String(length=10)),
        sa.Column("model_year_gregorian", sa.Integer()),
        sa.Column("inspection_expiry_raw", sa.Text()),
        sa.Column("inspection_expiry_month", sa.Date()),
        sa.Column("engine_cc", sa.Integer()),
        sa.Column("transmission", sa.String(length=20)),
        sa.Column("mileage_km", sa.Integer()),
        sa.Column("mileage_raw", sa.Text()),
        sa.Column("mileage_multiplier", sa.Integer()),
        sa.Column("mileage_inference_conf", sa.Numeric(3, 2)),
        sa.Column("score", sa.String(length=20)),
        sa.Column("score_numeric", sa.Numeric(3, 1)),
        sa.Column("color", sa.String(length=100)),
        sa.Column("result", sa.String(length=50)),
        sa.Column("starting_bid_yen", sa.Integer()),
        sa.Column("final_bid_yen", sa.Integer()),
        sa.Column(
            "starting_bid_man",
            sa.Integer(),
            sa.Computed("starting_bid_yen / 10000", persisted=True),
        ),
        sa.Column(
            "final_bid_man",
            sa.Integer(),
            sa.Computed("final_bid_yen / 10000", persisted=True),
        ),
        sa.Column("lane_type", sa.String(length=50)),
        sa.Column("equipment_codes", sa.Text()),
        sa.Column("make_ja", sa.String(length=100)),
        sa.Column("make_en", sa.String(length=100)),
        sa.Column("model_ja", sa.String(length=100)),
        sa.Column("model_en", sa.String(length=100)),
        sa.Column("inspector_notes", postgresql.JSONB()),
        sa.Column("damage_locations", postgresql.JSONB()),
        sa.Column("notes_text", sa.Text()),
        sa.Column("options_text", sa.Text()),
        sa.Column("full_text", sa.Text()),
        sa.Column("evidence", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("needs_review", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("review_reason", sa.Text()),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("overall_confidence", sa.Numeric(3, 2)),
        sa.Column(
            "fts_vector_en",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', "
                "coalesce(lot_no, '') || ' ' || "
                "coalesce(auction_venue, '') || ' ' || "
                "coalesce(auction_venue_round, '') || ' ' || "
                "coalesce(make_model, '') || ' ' || "
                "coalesce(model_code, '') || ' ' || "
                "coalesce(chassis_no, '') || ' ' || "
                "coalesce(notes_text, '') || ' ' || "
                "coalesce(options_text, '') || ' ' || "
                "coalesce(full_text, '')",
                persisted=True,
            ),
        ),
        sa.Column(
            "search_text",
            sa.Text(),
            sa.Computed(
                "coalesce(lot_no, '') || ' ' || "
                "coalesce(auction_venue, '') || ' ' || "
                "coalesce(auction_venue_round, '') || ' ' || "
                "coalesce(make_model, '') || ' ' || "
                "coalesce(make_ja, '') || ' ' || "
                "coalesce(make_en, '') || ' ' || "
                "coalesce(model_ja, '') || ' ' || "
                "coalesce(model_en, '') || ' ' || "
                "coalesce(model_code, '') || ' ' || "
                "coalesce(chassis_no, '') || ' ' || "
                "coalesce(notes_text, '') || ' ' || "
                "coalesce(options_text, '')",
                persisted=True,
            ),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_records_document", "auction_records", ["document_id"])
    op.create_index("idx_records_auction_date", "auction_records", ["auction_date"])
    op.create_index("idx_records_auction_venue", "auction_records", ["auction_venue"])
    op.create_index("idx_records_lot", "auction_records", ["lot_no"])
    op.create_index("idx_records_make_model", "auction_records", ["make_model"])
    op.create_index("idx_records_model_code", "auction_records", ["model_code"])
    op.create_index("idx_records_chassis_no", "auction_records", ["chassis_no"])
    op.create_index("idx_records_mileage", "auction_records", ["mileage_km"])
    op.create_index("idx_records_score", "auction_records", ["score_numeric"])
    op.create_index("idx_records_price", "auction_records", ["final_bid_yen"])
    op.create_index(
        "idx_records_needs_review",
        "auction_records",
        ["needs_review"],
        postgresql_where=sa.text("needs_review = true"),
    )
    op.create_index("idx_records_fts_en", "auction_records", ["fts_vector_en"], postgresql_using="gin")
    op.create_index(
        "idx_records_make_model_trgm",
        "auction_records",
        ["make_model"],
        postgresql_using="gin",
        postgresql_ops={"make_model": "gin_trgm_ops"},
    )
    op.create_index(
        "idx_records_model_code_trgm",
        "auction_records",
        ["model_code"],
        postgresql_using="gin",
        postgresql_ops={"model_code": "gin_trgm_ops"},
    )
    op.create_index(
        "idx_records_chassis_no_trgm",
        "auction_records",
        ["chassis_no"],
        postgresql_using="gin",
        postgresql_ops={"chassis_no": "gin_trgm_ops"},
    )
    op.create_index(
        "idx_records_search_text_trgm",
        "auction_records",
        ["search_text"],
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )
    op.create_index(
        "idx_records_evidence",
        "auction_records",
        ["evidence"],
        postgresql_using="gin",
    )

    op.create_table(
        "equipment_codes",
        sa.Column("code", sa.String(length=20), primary_key=True),
        sa.Column("name_ja", sa.String(length=100)),
        sa.Column("name_en", sa.String(length=100)),
        sa.Column("category", sa.String(length=50)),
    )

    op.bulk_insert(
        sa.table(
            "equipment_codes",
            sa.column("code", sa.String),
            sa.column("name_ja", sa.String),
            sa.column("name_en", sa.String),
            sa.column("category", sa.String),
        ),
        [
            {"code": "AAC", "name_ja": "オートエアコン", "name_en": "Auto A/C", "category": "comfort"},
            {"code": "ナビ", "name_ja": "カーナビ", "name_en": "Navigation", "category": "electronics"},
            {"code": "SR", "name_ja": "サンルーフ", "name_en": "Sunroof", "category": "exterior"},
            {"code": "AW", "name_ja": "アルミホイール", "name_en": "Alloy Wheels", "category": "exterior"},
            {"code": "革", "name_ja": "革シート", "name_en": "Leather Seats", "category": "interior"},
            {"code": "PS", "name_ja": "パワーステアリング", "name_en": "Power Steering", "category": "mechanical"},
            {"code": "PW", "name_ja": "パワーウィンドウ", "name_en": "Power Windows", "category": "comfort"},
            {"code": "DR", "name_ja": "ドライブレコーダー", "name_en": "Dash Cam", "category": "electronics"},
        ],
    )

    op.create_table(
        "overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auction_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("old_value", sa.Text()),
        sa.Column("new_value", sa.Text()),
        sa.Column("reason", sa.Text()),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_overrides_record", "overrides", ["record_id"])
    op.create_index("idx_overrides_user", "overrides", ["user_id"])

    op.create_table(
        "whatsapp_meta",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL")),
        sa.Column("message_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("from_number", sa.String(length=50), nullable=False),
        sa.Column("chat_id", sa.String(length=255)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'received'")),
        sa.Column("error_message", sa.Text()),
        sa.Column("raw_payload", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_whatsapp_document", "whatsapp_meta", ["document_id"])
    op.create_index("idx_whatsapp_status", "whatsapp_meta", ["status"])

    op.create_table(
        "extraction_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("regions", postgresql.JSONB(), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    op.execute(
        """
        CREATE TRIGGER trg_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

        CREATE TRIGGER trg_documents_updated_at
        BEFORE UPDATE ON documents
        FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

        CREATE TRIGGER trg_auction_records_updated_at
        BEFORE UPDATE ON auction_records
        FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

        CREATE TRIGGER trg_whatsapp_meta_updated_at
        BEFORE UPDATE ON whatsapp_meta
        FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

        CREATE TRIGGER trg_extraction_templates_updated_at
        BEFORE UPDATE ON extraction_templates
        FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
        """
    )

    op.execute(
        """
        CREATE VIEW review_queue AS
        SELECT ar.*, d.original_path, d.thumb_path, d.source
        FROM auction_records ar
        JOIN documents d ON ar.document_id = d.id
        WHERE ar.needs_review = true
        ORDER BY ar.created_at DESC;
        """
    )

    op.execute(
        """
        CREATE VIEW recent_records AS
        SELECT ar.*, d.original_path, d.thumb_path, d.source, d.status as document_status
        FROM auction_records ar
        JOIN documents d ON ar.document_id = d.id
        ORDER BY ar.created_at DESC
        LIMIT 100;
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS recent_records")
    op.execute("DROP VIEW IF EXISTS review_queue")

    op.execute("DROP TRIGGER IF EXISTS trg_extraction_templates_updated_at ON extraction_templates")
    op.execute("DROP TRIGGER IF EXISTS trg_whatsapp_meta_updated_at ON whatsapp_meta")
    op.execute("DROP TRIGGER IF EXISTS trg_auction_records_updated_at ON auction_records")
    op.execute("DROP TRIGGER IF EXISTS trg_documents_updated_at ON documents")
    op.execute("DROP TRIGGER IF EXISTS trg_users_updated_at ON users")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at")

    op.drop_table("extraction_templates")
    op.drop_table("whatsapp_meta")
    op.drop_index("idx_overrides_user", table_name="overrides")
    op.drop_index("idx_overrides_record", table_name="overrides")
    op.drop_table("overrides")
    op.drop_table("equipment_codes")

    op.drop_index("idx_records_evidence", table_name="auction_records")
    op.drop_index("idx_records_search_text_trgm", table_name="auction_records")
    op.drop_index("idx_records_chassis_no_trgm", table_name="auction_records")
    op.drop_index("idx_records_model_code_trgm", table_name="auction_records")
    op.drop_index("idx_records_make_model_trgm", table_name="auction_records")
    op.drop_index("idx_records_fts_en", table_name="auction_records")
    op.drop_index("idx_records_needs_review", table_name="auction_records")
    op.drop_index("idx_records_price", table_name="auction_records")
    op.drop_index("idx_records_score", table_name="auction_records")
    op.drop_index("idx_records_mileage", table_name="auction_records")
    op.drop_index("idx_records_chassis_no", table_name="auction_records")
    op.drop_index("idx_records_model_code", table_name="auction_records")
    op.drop_index("idx_records_make_model", table_name="auction_records")
    op.drop_index("idx_records_lot", table_name="auction_records")
    op.drop_index("idx_records_auction_venue", table_name="auction_records")
    op.drop_index("idx_records_auction_date", table_name="auction_records")
    op.drop_index("idx_records_document", table_name="auction_records")
    op.drop_table("auction_records")

    op.drop_index("idx_documents_source", table_name="documents")
    op.drop_index("idx_documents_created", table_name="documents")
    op.drop_index("idx_documents_status", table_name="documents")
    op.drop_table("documents")

    op.drop_index("idx_users_email", table_name="users")
    op.drop_table("users")

    op.execute('DROP EXTENSION IF EXISTS "pg_trgm"')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
