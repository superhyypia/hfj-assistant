import os
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(DATABASE_URL)


def check_db_health():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            result = cur.fetchone()
            return result[0] == 1


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
                ALTER TABLE ai_country_support_cache
                ADD COLUMN IF NOT EXISTS language TEXT NOT NULL DEFAULT 'en'
                """
            )

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

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS hfj_conversations (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    assistant_reply TEXT NOT NULL,
                    response_type TEXT,
                    title TEXT,
                    source TEXT,
                    source_site TEXT,
                    source_name TEXT,
                    source_domain TEXT,
                    agent_action TEXT,
                    agent_reason TEXT,
                    score DOUBLE PRECISION,
                    region_detected TEXT,
                    language TEXT,
                    is_fallback BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
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

            cur.executemany(
                """
                INSERT INTO hfj_sources
                (name, domain, base_url, region, source_type, priority, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (domain) DO NOTHING
                """,
                [
                    (
                        "Hope for Justice",
                        "hopeforjustice.org",
                        "https://hopeforjustice.org/human-trafficking/",
                        "global",
                        "official",
                        100,
                        "active",
                    ),
                    (
                        "HSE Ireland",
                        "hse.ie",
                        "https://www2.hse.ie/services/human-trafficking/",
                        "ireland",
                        "official",
                        95,
                        "active",
                    ),
                    (
                        "UK Modern Slavery Helpline",
                        "modernslaveryhelpline.org",
                        "https://www.modernslaveryhelpline.org/",
                        "uk",
                        "secondary",
                        85,
                        "active",
                    ),
                    (
                        "Citizens Information Ireland",
                        "citizensinformation.ie",
                        "https://www.citizensinformation.ie/en/justice/crime-and-crime-prevention/human-trafficking/",
                        "ireland",
                        "official",
                        96,
                        "active",
                    ),
                    (
                        "Royal Canadian Mounted Police",
                        "rcmp.ca",
                        "https://rcmp.ca/en/human-trafficking-recognizing-and-reporting/human-trafficking-works",
                        "canada",
                        "official",
                        88,
                        "active",
                    ),
                    (
                        "US National Human Trafficking Hotline",
                        "humantraffickinghotline.org",
                        "https://humantraffickinghotline.org/en/contact",
                        "united_states",
                        "official",
                        92,
                        "active",
                    ),
                ],
            )

        conn.commit()


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


def log_conversation_turn(
    session_id: str,
    user_message: str,
    assistant_reply: str,
    response_type: str | None = None,
    title: str | None = None,
    source: str | None = None,
    source_site: str | None = None,
    source_name: str | None = None,
    source_domain: str | None = None,
    agent_action: str | None = None,
    agent_reason: str | None = None,
    score: float | None = None,
    region_detected: str | None = None,
    language: str | None = None,
    is_fallback: bool = False,
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO hfj_conversations (
                    session_id,
                    user_message,
                    assistant_reply,
                    response_type,
                    title,
                    source,
                    source_site,
                    source_name,
                    source_domain,
                    agent_action,
                    agent_reason,
                    score,
                    region_detected,
                    language,
                    is_fallback
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    user_message,
                    assistant_reply,
                    response_type,
                    title,
                    source,
                    source_site,
                    source_name,
                    source_domain,
                    agent_action,
                    agent_reason,
                    score,
                    region_detected,
                    language,
                    is_fallback,
                ),
            )
        conn.commit()


def get_conversations(limit: int = 100):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    session_id,
                    user_message,
                    assistant_reply,
                    response_type,
                    title,
                    source,
                    source_site,
                    source_name,
                    source_domain,
                    agent_action,
                    agent_reason,
                    score,
                    region_detected,
                    language,
                    is_fallback,
                    created_at
                FROM hfj_conversations
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "id": r[0],
            "session_id": r[1],
            "user_message": r[2],
            "assistant_reply": r[3],
            "response_type": r[4],
            "title": r[5],
            "source": r[6],
            "source_site": r[7],
            "source_name": r[8],
            "source_domain": r[9],
            "agent_action": r[10],
            "agent_reason": r[11],
            "score": r[12],
            "region_detected": r[13],
            "language": r[14],
            "is_fallback": r[15],
            "created_at": r[16].isoformat() if r[16] else None,
        }
        for r in rows
    ]


def get_conversation_by_id(conversation_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    session_id,
                    user_message,
                    assistant_reply,
                    response_type,
                    title,
                    source,
                    source_site,
                    source_name,
                    source_domain,
                    agent_action,
                    agent_reason,
                    score,
                    region_detected,
                    language,
                    is_fallback,
                    created_at
                FROM hfj_conversations
                WHERE id = %s
                """,
                (conversation_id,),
            )
            r = cur.fetchone()

    if not r:
        return None

    return {
        "id": r[0],
        "session_id": r[1],
        "user_message": r[2],
        "assistant_reply": r[3],
        "response_type": r[4],
        "title": r[5],
        "source": r[6],
        "source_site": r[7],
        "source_name": r[8],
        "source_domain": r[9],
        "agent_action": r[10],
        "agent_reason": r[11],
        "score": r[12],
        "region_detected": r[13],
        "language": r[14],
        "is_fallback": r[15],
        "created_at": r[16].isoformat() if r[16] else None,
    }
