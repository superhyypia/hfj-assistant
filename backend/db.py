import os
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL")


# =========================
# Connection
# =========================
def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(DATABASE_URL)


# =========================
# Health Check
# =========================
def check_db_health():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            result = cur.fetchone()
            return result[0] == 1


# =========================
# Init DB (tables + seeds)
# =========================
def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:

            # -------------------------
            # Support Routes
            # -------------------------
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS hfj_support_routes (
                    region_key TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    emergency_text TEXT,
                    phone TEXT,
                    website TEXT
                )
                """
            )

            # -------------------------
            # Content Chunks (RAG)
            # -------------------------
            cur.execute(
                """
            CREATE TABLE IF NOT EXISTS hfj_content_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    source_id BIGINT,
                    source_name TEXT,
                    source_domain TEXT,
                    source_url TEXT NOT NULL,
                    source_site TEXT NOT NULL DEFAULT 'hopeforjustice',
                    region TEXT NOT NULL DEFAULT 'global',
                    content_type TEXT NOT NULL DEFAULT 'education',
                    page_title TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    section_heading TEXT,
                    content TEXT NOT NULL,
                    embedding_json TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(source_url, chunk_index)
                )
                """
            )

            cur.execute(
            """
            ALTER TABLE hfj_content_chunks
                ADD COLUMN IF NOT EXISTS source_id BIGINT
                """
            )
            cur.execute(
                """
                ALTER TABLE hfj_content_chunks
                ADD COLUMN IF NOT EXISTS source_name TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE hfj_content_chunks
                ADD COLUMN IF NOT EXISTS source_domain TEXT
                """
            )

            # -------------------------
            # AI Cache
            # -------------------------
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_country_support_cache (
                    country_key TEXT PRIMARY KEY,
                    country_name TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'en',
                    payload_json TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

            # -------------------------
            # NEW: Sources Table (Admin)
            # -------------------------
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS hfj_sources (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    domain TEXT NOT NULL UNIQUE,
                    base_url TEXT,
                    region TEXT NOT NULL DEFAULT 'global',
                    source_type TEXT NOT NULL DEFAULT 'official',
                    priority INTEGER NOT NULL DEFAULT 100,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

            # -------------------------
            # Seed Support Routes
            # -------------------------
            cur.executemany(
                """
                INSERT INTO hfj_support_routes
                (region_key, display_name, emergency_text, phone, website)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (region_key) DO NOTHING
                """,
                [
                    ("ireland", "Ireland", "Call 112 or 999 if there is immediate danger.", "01 795 8280", "https://www2.hse.ie/services/human-trafficking/"),
                    ("uk", "United Kingdom", "Call 999 if there is immediate danger.", "0800 0121 700", "https://www.modernslavery.gov.uk/"),
                    ("united_states", "United States", "Call 911 if there is immediate danger.", "1-888-373-7888", "https://humantraffickinghotline.org/en/contact"),
                    ("canada", "Canada", "Call 911 if there is immediate danger.", "1-833-900-1010", "https://www.canadianhumantraffickinghotline.ca/"),
                    ("belgium", "Belgium", "Contact local emergency services if there is immediate danger.", None, "https://hopeforjustice.org/get-help/"),
                ],
            )

            # -------------------------
            # Seed Sources
            # -------------------------
            cur.executemany(
                """
                INSERT INTO hfj_sources
                (name, domain, base_url, region, source_type, priority, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (domain) DO NOTHING
                """,
                [
                    ("Hope for Justice", "hopeforjustice.org", "https://hopeforjustice.org/", "global", "official", 100, "active"),
                    ("HSE", "hse.ie", "https://www2.hse.ie/services/human-trafficking/", "ireland", "official", 95, "active"),
                    ("Modern Slavery Helpline", "modernslaveryhelpline.org", "https://www.modernslaveryhelpline.org/", "uk", "secondary", 85, "active"),
                ],
            )

        conn.commit()


# =========================
# Queries
# =========================
def get_sources():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, domain, base_url, region, source_type, priority, status, created_at
                FROM hfj_sources
                ORDER BY priority DESC, name ASC
                """
            )
            rows = cur.fetchall()

    return [
        {
            "id": r[0],
            "name": r[1],
            "domain": r[2],
            "base_url": r[3],
            "region": r[4],
            "source_type": r[5],
            "priority": r[6],
            "status": r[7],
            "created_at": r[8].isoformat() if r[8] else None,
        }
        for r in rows
    ]
