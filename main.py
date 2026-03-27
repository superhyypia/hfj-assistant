from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

import os
import uuid
import re
import requests
import pycountry
import psycopg
from bs4 import BeautifulSoup

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None
database_url = os.getenv("DATABASE_URL")

SESSION_STATE = {}

CONTENT_SOURCES = [
    {
        "url": "https://hopeforjustice.org/human-trafficking/",
        "source_site": "hopeforjustice",
        "region": "global",
        "content_type": "education",
    },
    {
        "url": "https://hopeforjustice.org/spot-the-signs/",
        "source_site": "hopeforjustice",
        "region": "global",
        "content_type": "education",
    },
    {
        "url": "https://hopeforjustice.org/get-help/",
        "source_site": "hopeforjustice",
        "region": "global",
        "content_type": "support",
    },
    {
        "url": "https://hopeforjustice.org/contact/",
        "source_site": "hopeforjustice",
        "region": "global",
        "content_type": "support",
    },
    {
        "url": "https://hopeforjustice.org/resources-and-statistics/",
        "source_site": "hopeforjustice",
        "region": "global",
        "content_type": "resource",
    },
    {
        "url": "https://hopeforjustice.org/resources-and-statistics/spot-the-signs-resources/",
        "source_site": "hopeforjustice",
        "region": "global",
        "content_type": "resource",
    },
    {
        "url": "https://www2.hse.ie/services/human-trafficking/",
        "source_site": "hse",
        "region": "ireland",
        "content_type": "support",
    },
    {
        "url": "https://www2.hse.ie/services/domestic-sexual-gender-based-violence/",
        "source_site": "hse",
        "region": "ireland",
        "content_type": "support",
    },
    {
        "url": "https://www.modernslavery.gov.uk/",
        "source_site": "modernslavery_uk",
        "region": "uk",
        "content_type": "reporting",
    },
    {
        "url": "https://www.modernslavery.gov.uk/prompt-sheet-for-working-offline",
        "source_site": "modernslavery_uk",
        "region": "uk",
        "content_type": "reporting",
    },
]

USER_AGENT = "Mozilla/5.0 (compatible; HFJ-Assistant-MVP/1.1)"

JUNK_PATTERNS = [
    "out of date browser",
    "update your browser",
    "we use cookies",
    "privacy policy",
    "cookie settings",
    "accept cookies",
    "terms and conditions",
    "all rights reserved",
    "skip to content",
    "manage consent",
    "close this notice",
    "phone this field is for validation purposes",
    "sign up to our email updates",
]

US_STATES = {
    "alabama": "Alabama",
    "alaska": "Alaska",
    "arizona": "Arizona",
    "arkansas": "Arkansas",
    "california": "California",
    "colorado": "Colorado",
    "connecticut": "Connecticut",
    "delaware": "Delaware",
    "florida": "Florida",
    "georgia": "Georgia",
    "hawaii": "Hawaii",
    "idaho": "Idaho",
    "illinois": "Illinois",
    "indiana": "Indiana",
    "iowa": "Iowa",
    "kansas": "Kansas",
    "kentucky": "Kentucky",
    "louisiana": "Louisiana",
    "maine": "Maine",
    "maryland": "Maryland",
    "massachusetts": "Massachusetts",
    "michigan": "Michigan",
    "minnesota": "Minnesota",
    "mississippi": "Mississippi",
    "missouri": "Missouri",
    "montana": "Montana",
    "nebraska": "Nebraska",
    "nevada": "Nevada",
    "new hampshire": "New Hampshire",
    "new jersey": "New Jersey",
    "new mexico": "New Mexico",
    "new york": "New York",
    "north carolina": "North Carolina",
    "north dakota": "North Dakota",
    "ohio": "Ohio",
    "oklahoma": "Oklahoma",
    "oregon": "Oregon",
    "pennsylvania": "Pennsylvania",
    "rhode island": "Rhode Island",
    "south carolina": "South Carolina",
    "south dakota": "South Dakota",
    "tennessee": "Tennessee",
    "texas": "Texas",
    "utah": "Utah",
    "vermont": "Vermont",
    "virginia": "Virginia",
    "washington": "Washington",
    "west virginia": "West Virginia",
    "wisconsin": "Wisconsin",
    "wyoming": "Wyoming",
    "district of columbia": "District of Columbia",
}

STATE_ABBREVIATIONS = {
    "al": "Alabama",
    "ak": "Alaska",
    "az": "Arizona",
    "ar": "Arkansas",
    "ca": "California",
    "co": "Colorado",
    "ct": "Connecticut",
    "de": "Delaware",
    "fl": "Florida",
    "ga": "Georgia",
    "hi": "Hawaii",
    "id": "Idaho",
    "il": "Illinois",
    "in": "Indiana",
    "ia": "Iowa",
    "ks": "Kansas",
    "ky": "Kentucky",
    "la": "Louisiana",
    "me": "Maine",
    "md": "Maryland",
    "ma": "Massachusetts",
    "mi": "Michigan",
    "mn": "Minnesota",
    "ms": "Mississippi",
    "mo": "Missouri",
    "mt": "Montana",
    "ne": "Nebraska",
    "nv": "Nevada",
    "nh": "New Hampshire",
    "nj": "New Jersey",
    "nm": "New Mexico",
    "ny": "New York",
    "nc": "North Carolina",
    "nd": "North Dakota",
    "oh": "Ohio",
    "ok": "Oklahoma",
    "or": "Oregon",
    "pa": "Pennsylvania",
    "ri": "Rhode Island",
    "sc": "South Carolina",
    "sd": "South Dakota",
    "tn": "Tennessee",
    "tx": "Texas",
    "ut": "Utah",
    "vt": "Vermont",
    "va": "Virginia",
    "wa": "Washington",
    "wv": "West Virginia",
    "wi": "Wisconsin",
    "wy": "Wyoming",
    "dc": "District of Columbia",
}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


def get_db_connection():
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(database_url)


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def normalize_whitespace(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_country_key(name: str) -> str:
    name = name.lower().strip()
    mapping = {
        "uk": "uk",
        "united kingdom": "uk",
        "great britain": "uk",
        "england": "uk",
        "scotland": "uk",
        "wales": "uk",
        "northern ireland": "uk",
        "us": "united_states",
        "usa": "united_states",
        "u.s.": "united_states",
        "u.s.a.": "united_states",
        "united states": "united_states",
        "united states of america": "united_states",
    }
    return mapping.get(name, name.replace(" ", "_"))


def slugify_state(state_name: str) -> str:
    return state_name.lower().replace(" ", "-")


def is_help_trigger(text: str) -> bool:
    triggers = [
        "i need help",
        "help me",
        "i think i am being trafficked",
        "i think i'm being trafficked",
        "i am being trafficked",
        "i'm being trafficked",
        "someone is being controlled",
        "someone is being exploited",
        "i think this is trafficking",
        "report trafficking",
        "i am trapped",
        "i'm trapped",
        "i cannot leave",
        "i can't leave",
        "someone cannot leave",
        "someone can't leave",
    ]
    return any(t in text for t in triggers)


def looks_like_general_question(text: str) -> bool:
    triggers = [
        "what is",
        "what's",
        "how do i spot",
        "spot the signs",
        "signs of trafficking",
        "what are the signs",
        "human trafficking",
        "labour trafficking",
        "labor trafficking",
        "sex trafficking",
        "sexual exploitation",
        "forced sexual exploitation",
        "forced labour",
        "forced labor",
        "define trafficking",
        "meaning of trafficking",
        "warning signs",
        "indicators of trafficking",
        "indicators of exploitation",
    ]
    return any(t in text for t in triggers)


def is_junk(text: str) -> bool:
    t = text.lower()
    return any(pattern in t for pattern in JUNK_PATTERNS)


def detect_us_state(text: str, original: str) -> dict | None:
    for key, value in US_STATES.items():
        if re.search(rf"\b{re.escape(key)}\b", text):
            return {"kind": "state", "value": value, "confidence": "high"}

    upper_tokens = re.findall(r"\b[A-Z]{2}\b", original)
    for token in upper_tokens:
        token_lower = token.lower()
        if token_lower in STATE_ABBREVIATIONS:
            return {
                "kind": "state",
                "value": STATE_ABBREVIATIONS[token_lower],
                "confidence": "medium",
            }

    return None


def detect_country_with_library(user_input: str) -> dict | None:
    text = user_input.strip().lower()

    for country in pycountry.countries:
        names_to_check = {country.name.lower()}

        official_name = getattr(country, "official_name", None)
        if official_name:
            names_to_check.add(official_name.lower())

        common_name = getattr(country, "common_name", None)
        if common_name:
            names_to_check.add(common_name.lower())

        for name in names_to_check:
            if re.search(rf"\b{re.escape(name)}\b", text):
                return {
                    "kind": "country",
                    "value": country.name,
                    "confidence": "high",
                }

    try:
        result = pycountry.countries.search_fuzzy(user_input.strip())
        if result:
            return {
                "kind": "country",
                "value": result[0].name,
                "confidence": "medium",
            }
    except LookupError:
        pass

    return None


def detect_location(user_input: str, text: str) -> dict | None:
    state_result = detect_us_state(text, user_input)
    if state_result:
        return state_result

    country_result = detect_country_with_library(user_input)
    if country_result:
        return country_result

    return None


def add_safety_footer(text: str) -> str:
    return (
        text.strip()
        + "\n\nIf someone may be in danger, please seek help from official services immediately."
    )


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
                    source_site TEXT NOT NULL,
                    region TEXT NOT NULL DEFAULT 'global',
                    content_type TEXT NOT NULL DEFAULT 'education',
                    page_title TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    section_heading TEXT,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(source_url, chunk_index)
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
        conn.commit()


def fetch_page_html(url: str) -> str:
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    return response.text


def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    text = normalize_whitespace(text)
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current = ""

    for p in paragraphs:
        if len(current) + len(p) + 1 <= max_chars:
            current = f"{current}\n{p}".strip()
        else:
            if current:
                chunks.append(current)
            if len(p) <= max_chars:
                current = p
            else:
                for i in range(0, len(p), max_chars):
                    part = p[i:i + max_chars].strip()
                    if part:
                        chunks.append(part)
                current = ""

    if current:
        chunks.append(current)

    return chunks


def parse_page(html: str, url: str, source_site: str, region: str, content_type: str) -> tuple[str, list[dict]]:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "iframe", "svg", "form"]):
        tag.decompose()

    for selector in ["header", "footer", "nav"]:
        for tag in soup.select(selector):
            tag.decompose()

    main_content = soup.find("main")
    article_content = soup.find("article")
    root = article_content or main_content or soup

    page_title = "Content"
    h1 = root.find("h1")
    if h1:
        page_title = normalize_whitespace(h1.get_text(" ", strip=True))
    elif soup.title:
        page_title = normalize_whitespace(soup.title.get_text(" ", strip=True))

    nodes = root.find_all(["h2", "h3", "p", "li"])
    sections = []
    current_heading = page_title
    buffer = []

    def flush_buffer():
        nonlocal buffer
        if not buffer:
            return
        joined = "\n".join(buffer).strip()
        for chunk in chunk_text(joined):
            sections.append(
                {
                    "source_url": url,
                    "source_site": source_site,
                    "region": region,
                    "content_type": content_type,
                    "page_title": page_title,
                    "section_heading": current_heading,
                    "content": chunk,
                }
            )
        buffer = []

    for node in nodes:
        text = normalize_whitespace(node.get_text(" ", strip=True))

        if not text or len(text) < 20:
            continue

        if is_junk(text):
            continue

        if node.name in ["h2", "h3"]:
            flush_buffer()
            current_heading = text
        else:
            buffer.append(text)

    flush_buffer()
    return page_title, sections


def upsert_sections(sections: list[dict]) -> int:
    if not sections:
        return 0

    rows = []
    for idx, section in enumerate(sections, start=1):
        rows.append(
            (
                section["source_url"],
                section["source_site"],
                section["region"],
                section["content_type"],
                section["page_title"],
                idx,
                section["section_heading"],
                section["content"],
            )
        )

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            source_url = sections[0]["source_url"]
            cur.execute(
                "DELETE FROM hfj_content_chunks WHERE source_url = %s",
                (source_url,),
            )
            cur.executemany(
                """
                INSERT INTO hfj_content_chunks
                (source_url, source_site, region, content_type, page_title, chunk_index, section_heading, content)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
        conn.commit()

    return len(rows)


def ingest_all_sources():
    results = []

    for source in CONTENT_SOURCES:
        try:
            html = fetch_page_html(source["url"])
            page_title, sections = parse_page(
                html=html,
                url=source["url"],
                source_site=source["source_site"],
                region=source["region"],
                content_type=source["content_type"],
            )
            count = upsert_sections(sections)
            results.append(
                {
                    "url": source["url"],
                    "source_site": source["source_site"],
                    "region": source["region"],
                    "content_type": source["content_type"],
                    "page_title": page_title,
                    "chunks_ingested": count,
                    "status": "ok",
                }
            )
        except Exception as e:
            results.append(
                {
                    "url": source["url"],
                    "source_site": source["source_site"],
                    "status": "error",
                    "error": str(e),
                }
            )

    return results


@app.on_event("startup")
def startup_event():
    init_db()
    ingest_all_sources()


def get_support_route(region_key: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT region_key, display_name, emergency_text, phone, website
                FROM hfj_support_routes
                WHERE region_key = %s
                """,
                (region_key,),
            )
            row = cur.fetchone()

    if not row:
        return None

    return {
        "region_key": row[0],
        "display_name": row[1],
        "emergency_text": row[2],
        "phone": row[3],
        "website": row[4],
    }


def score_chunk(
    query: str,
    title: str,
    heading: str | None,
    content: str,
    source_site: str,
    region: str,
    content_type: str,
    user_region: str | None,
) -> float:
    query_terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
    if not query_terms:
        return 0.0

    title_l = (title or "").lower()
    heading_l = (heading or "").lower()
    content_l = (content or "").lower()
    query_l = query.lower()

    score = 0.0

    for term in query_terms:
        if term in title_l:
            score += 4.0
        if term in heading_l:
            score += 3.0
        if term in content_l:
            score += 1.0

    exact_phrases = [
        "human trafficking",
        "spot the signs",
        "warning signs",
        "get help",
        "forced labour",
        "forced labor",
        "sex trafficking",
        "sexual exploitation",
        "forced sexual exploitation",
        "report modern slavery",
    ]

    for phrase in exact_phrases:
        if phrase in query_l and (
            phrase in title_l or phrase in heading_l or phrase in content_l
        ):
            score += 5.0

    if user_region and region == user_region:
        score += 6.0

    if user_region == "ireland" and source_site == "hse":
        score += 4.0

    if user_region == "uk" and source_site == "modernslavery_uk":
        score += 4.0

    if "report" in query_l and content_type == "reporting":
        score += 4.0

    if "help" in query_l and content_type == "support":
        score += 4.0

    if (
        "sign" in query_l
        or "what is" in query_l
        or "what are the signs" in query_l
        or "sexual exploitation" in query_l
    ) and content_type == "education":
        score += 3.0

    return score


def infer_user_region(location: dict | None) -> str | None:
    if not location:
        return None

    if location["kind"] == "state":
        return "united_states"

    key = normalize_country_key(location["value"])
    if key in {"ireland", "uk", "united_states"}:
        return key
    return None


def find_match(query: str, user_region: str | None = None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_url, source_site, region, content_type, page_title, section_heading, content
                FROM hfj_content_chunks
                """
            )
            rows = cur.fetchall()

    scored = []

    for row in rows:
        score = score_chunk(
            query=query,
            title=row[4],
            heading=row[5],
            content=row[6],
            source_site=row[1],
            region=row[2],
            content_type=row[3],
            user_region=user_region,
        )
        if score > 1:
            scored.append((score, row))

    scored.sort(reverse=True, key=lambda x: x[0])

    if not scored:
        return None

    top_chunks = [row for _, row in scored[:3]]
    combined = "\n\n".join(chunk[6] for chunk in top_chunks)

    return {
        "source": top_chunks[0][0],
        "source_site": top_chunks[0][1],
        "region": top_chunks[0][2],
        "content_type": top_chunks[0][3],
        "title": top_chunks[0][4],
        "section_heading": top_chunks[0][5],
        "answer": combined[:1400],
    }


def build_us_state_response(state_name: str):
    state_slug = slugify_state(state_name)
    state_page = f"https://humantraffickinghotline.org/en/statistics/{state_slug}"

    return {
        "reply": (
            f"If you are in {state_name}:\n\n"
            "• If there is immediate danger, call 911 now\n"
            "• National Human Trafficking Hotline: 1-888-373-7888\n"
            "• Text: 233733\n"
            "• Live chat and online reporting are also available\n\n"
            f"The National Human Trafficking Hotline also has a dedicated {state_name} page, "
            "and I’ve included the local services directory below."
        ),
        "source": state_page,
        "extra_sources": [
            "https://humantraffickinghotline.org/en/contact",
            "https://humantraffickinghotline.org/en/find-local-services",
        ],
        "type": "hfj",
        "title": f"Support in {state_name}",
    }


def build_country_response(country_name: str):
    country_key = normalize_country_key(country_name)
    route = get_support_route(country_key)

    if route:
        reply_lines = [
            f"If you are in {route['display_name']}:",
            "",
            f"• {route['emergency_text']}",
        ]

        if route["phone"]:
            reply_lines.append(f"• Support contact: {route['phone']}")

        if route["website"]:
            reply_lines.append(f"• Website: {route['website']}")

        return {
            "reply": "\n".join(reply_lines),
            "source": route["website"] or "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": f"Support in {route['display_name']}",
        }

    display_name = country_name.strip()
    return {
        "reply": (
            f"If you are in {display_name}:\n\n"
            "• If there is immediate danger, contact local emergency services right away\n"
            "• Seek help from official local authorities or trusted local support organisations\n\n"
            "I do not want to guess country-specific contact details. "
            "I’ve included Hope for Justice help information below while you seek the appropriate local official support."
        ),
        "source": "https://hopeforjustice.org/get-help/",
        "type": "hfj",
        "title": f"Support in {display_name}",
    }


def build_help_prompt(location: dict | None, session_id: str):
    if location and location["confidence"] == "high":
        return {
            "reply": (
                "I’m really sorry this may be happening.\n\n"
                "If there is immediate danger, contact emergency services now.\n\n"
                f"I understand you may be in {location['value']}. "
                "I can give you the safest support options for that location."
            ),
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": "Immediate support",
            "session_id": session_id,
        }

    return {
        "reply": (
            "I’m really sorry this may be happening.\n\n"
            "If there is immediate danger, contact emergency services now.\n\n"
            "Please tell me your country or state and I’ll give you the right support options."
        ),
        "source": "https://hopeforjustice.org/get-help/",
        "type": "hfj",
        "title": "Immediate support",
        "session_id": session_id,
    }


@app.get("/")
def root():
    return {"message": "HFJ Assistant is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db-check")
def db_check():
    try:
        ireland = get_support_route("ireland")
        uk = get_support_route("uk")
        us = get_support_route("united_states")

        return {
            "status": "ok",
            "database_connected": True,
            "sample_routes": {
                "ireland": ireland,
                "uk": uk,
                "united_states": us,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/routes")
def routes():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT region_key, display_name, emergency_text, phone, website
                    FROM hfj_support_routes
                    ORDER BY display_name
                    """
                )
                rows = cur.fetchall()

        return {
            "routes": [
                {
                    "region_key": row[0],
                    "display_name": row[1],
                    "emergency_text": row[2],
                    "phone": row[3],
                    "website": row[4],
                }
                for row in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/content-check")
def content_check():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source_site, region, content_type, page_title, COUNT(*)
                    FROM hfj_content_chunks
                    GROUP BY source_site, region, content_type, page_title
                    ORDER BY source_site, page_title
                    """
                )
                rows = cur.fetchall()

        return {
            "pages": [
                {
                    "source_site": row[0],
                    "region": row[1],
                    "content_type": row[2],
                    "page_title": row[3],
                    "chunk_count": row[4],
                }
                for row in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/reingest-all")
def reingest_all():
    try:
        results = ingest_all_sources()
        return {"status": "ok", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest error: {str(e)}")


@app.post("/chat")
def chat(req: ChatRequest):
    user_input = req.message.strip()
    text = normalize(user_input)

    if not user_input:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    session_id = req.session_id or str(uuid.uuid4())
    session = SESSION_STATE.setdefault(
        session_id,
        {
            "stage": None,
            "saved_location": None,
        },
    )

    # Break out of pending support flow if the user asks a general education question.
    if session["stage"] == "awaiting_location" and looks_like_general_question(text):
        session["stage"] = None
        session["saved_location"] = None

    if session["stage"] == "awaiting_location":
        location = detect_location(user_input, text)

        if location:
            session["stage"] = None
            session["saved_location"] = None

            if location["kind"] == "state":
                result = build_us_state_response(location["value"])
            else:
                result = build_country_response(location["value"])

            result["session_id"] = session_id
            return result

        return {
            "reply": "Please tell me your country or state so I can give you the right support options.",
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": "Location needed",
            "session_id": session_id,
        }

    location = detect_location(user_input, text)
    if location:
        if location.get("kind") == "state":
            result = build_us_state_response(location["value"])
            result["session_id"] = session_id
            return result

        if location.get("kind") == "country":
            result = build_country_response(location["value"])
            result["session_id"] = session_id
            return result

    # Educational retrieval should win before support flow for knowledge questions.
    if looks_like_general_question(text):
        user_region = infer_user_region(detect_location(user_input, text))
        match = find_match(text, user_region=user_region)
        if match:
            return {
                "reply": add_safety_footer(match["answer"]),
                "source": match["source"],
                "type": "hfj",
                "title": match["title"],
                "section_heading": match["section_heading"],
                "source_site": match["source_site"],
                "session_id": session_id,
            }

    if is_help_trigger(text):
        detected_location = detect_location(user_input, text)

        if detected_location and detected_location["confidence"] == "high":
            if detected_location["kind"] == "state":
                result = build_us_state_response(detected_location["value"])
            else:
                result = build_country_response(detected_location["value"])

            result["reply"] = (
                "I’m really sorry this may be happening.\n\n"
                "If there is immediate danger, contact emergency services now.\n\n"
                + result["reply"]
            )
            result["session_id"] = session_id
            return result

        session["stage"] = "awaiting_location"
        return build_help_prompt(detected_location, session_id)

    user_region = infer_user_region(location)
    match = find_match(text, user_region=user_region)
    if match:
        return {
            "reply": add_safety_footer(match["answer"]),
            "source": match["source"],
            "type": "hfj",
            "title": match["title"],
            "section_heading": match["section_heading"],
            "source_site": match["source_site"],
            "session_id": session_id,
        }

    if not client:
        raise HTTPException(status_code=500, detail="Missing API key")

    response = client.responses.create(
        model="gpt-4o",
        input=f"""
You are the Hope for Justice assistant.

Provide clear, structured, calm, supportive answers about trafficking-related topics.
Do not provide investigative or vigilante advice.
If someone may need help, encourage official support routes.

Question: {user_input}
"""
    )

    return {
        "reply": response.output_text,
        "source": "AI-generated general guidance",
        "type": "ai",
        "title": "General guidance",
        "session_id": session_id,
    }
