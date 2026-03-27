import os
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(DATABASE_URL)


def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
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

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS hfj_content_chunks (
                    id BIGSERIAL PRIMARY KEY,
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
                CREATE TABLE IF NOT EXISTS ai_country_support_cache (
                    country_key TEXT PRIMARY KEY,
                    country_name TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'en',
                    payload_json TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

            cur.execute(
                """
                ALTER TABLE hfj_content_chunks
                ADD COLUMN IF NOT EXISTS source_site TEXT NOT NULL DEFAULT 'hopeforjustice'
                """
            )
            cur.execute(
                """
                ALTER TABLE hfj_content_chunks
                ADD COLUMN IF NOT EXISTS region TEXT NOT NULL DEFAULT 'global'
                """
            )
            cur.execute(
                """
                ALTER TABLE hfj_content_chunks
                ADD COLUMN IF NOT EXISTS content_type TEXT NOT NULL DEFAULT 'education'
                """
            )
            cur.execute(
                """
                ALTER TABLE hfj_content_chunks
                ADD COLUMN IF NOT EXISTS embedding_json TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE ai_country_support_cache
                ADD COLUMN IF NOT EXISTS language TEXT NOT NULL DEFAULT 'en'
                """
            )

            cur.executemany(
                """
                INSERT INTO hfj_support_routes
                (region_key, display_name, emergency_text, phone, website)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (region_key) DO NOTHING
                """,
                [
                    (
                        "ireland",
                        "Ireland",
                        "Call 112 or 999 if there is immediate danger.",
                        "01 795 8280",
                        "https://www2.hse.ie/services/human-trafficking/",
                    ),
                    (
                        "uk",
                        "United Kingdom",
                        "Call 999 if there is immediate danger.",
                        "0800 0121 700",
                        "https://www.modernslavery.gov.uk/",
                    ),
                    (
                        "united_states",
                        "United States",
                        "Call 911 if there is immediate danger.",
                        "1-888-373-7888",
                        "https://humantraffickinghotline.org/en/contact",
                    ),
                    (
                        "canada",
                        "Canada",
                        "Call 911 if there is immediate danger.",
                        "1-833-900-1010",
                        "https://www.canadianhumantraffickinghotline.ca/",
                    ),
                    (
                        "belgium",
                        "Belgium",
                        "Contact local emergency services if there is immediate danger.",
                        None,
                        "https://hopeforjustice.org/get-help/",
                    ),
                ],
            )

        conn.commit()
