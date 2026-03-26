from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

import os
import uuid
import re
import math
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

HFJ_PAGE_SOURCES = [
    "https://hopeforjustice.org/human-trafficking/",
    "https://hopeforjustice.org/spot-the-signs/",
    "https://hopeforjustice.org/get-help/",
    "https://hopeforjustice.org/contact/",
    "https://hopeforjustice.org/resources-and-statistics/",
    "https://hopeforjustice.org/resources-and-statistics/spot-the-signs-resources/",
]

USER_AGENT = (
    "Mozilla/5.0 (compatible; HFJ-Assistant-MVP/1.0; +https://hopeforjustice.org)"
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


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


def get_db_connection():
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(database_url)


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


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
        "help",
        "danger",
        "controlled",
        "trapped",
        "forced",
        "cannot leave",
        "can't leave",
        "being exploited",
        "someone is being exploited",
        "someone is being controlled",
        "i need help",
        "i think this is trafficking",
        "report trafficking",
        "i think i am being trafficked",
        "i think i'm being trafficked",
        "i am being trafficked",
        "i'm being trafficked",
    ]
    return any(t in text for t in triggers)


def is_yes(text: str) -> bool:
    yes_words = ["yes", "yeah", "y", "urgent", "in danger", "immediate danger"]
    return any(word == text or word in text for word in yes_words)


def is_no(text: str) -> bool:
    no_words = ["no", "nope", "not right now", "not immediate", "safe for now"]
    return any(word == text or word in text for word in no_words)


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
        common_name = getattr(country, "common_name", None)

        if official_name:
            names_to_check.add(official_name.lower())
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

    library_country = detect_country_with_library(user_input)
    if library_country:
        return library_country

    return None


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
                    page_title TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    section_heading TEXT,
                    content TEXT NOT NULL,
                    content_type TEXT NOT NULL DEFAULT 'education',
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
                # hard split very long paragraph
                for i in range(0, len(p), max_chars):
                    part = p[i:i + max_chars].strip()
                    if part:
                        chunks.append(part)
                current = ""

    if current:
        chunks.append(current)

    return chunks


def normalize_whitespace(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_hfj_page(html: str, url: str) -> tuple[str, list[dict]]:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "iframe", "svg", "form"]):
        tag.decompose()

    for selector in ["header", "footer", "nav"]:
        for tag in soup.select(selector):
            tag.decompose()

    page_title = "Hope for Justice"
    h1 = soup.find("h1")
    if h1:
        page_title = normalize_whitespace(h1.get_text(" ", strip=True))
    elif soup.title:
        page_title = normalize_whitespace(soup.title.get_text(" ", strip=True))

    nodes = soup.find_all(["h2", "h3", "p", "li"])
    sections: list[dict] = []
    current_heading = page_title
    buffer: list[str] = []

    def flush_buffer():
        nonlocal buffer
        if not buffer:
            return
        joined = "\n".join(buffer).strip()
        for chunk in chunk_text(joined):
            sections.append(
                {
                    "source_url": url,
                    "page_title": page_title,
                    "section_heading": current_heading,
                    "content": chunk,
                }
            )
        buffer = []

    for node in nodes:
        text = normalize_whitespace(node.get_text(" ", strip=True))
        if not text or len(text) < 3:
            continue

        if node.name in ["h2", "h3"]:
            flush_buffer()
            current_heading = text
        else:
            # filter obvious junk
            lowered = text.lower()
            if lowered in {"accept", "privacy policy"}:
                continue
            buffer.append(text)

    flush_buffer()
    return page_title, sections


def upsert_hfj_sections(sections: list[dict]):
    if not sections:
        return 0

    rows = []
    for idx, section in enumerate(sections, start=1):
        rows.append(
            (
                section["source_url"],
                section["page_title"],
                idx,
                section["section_heading"],
                section["content"],
                "education",
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
                (source_url, page_title, chunk_index, section_heading, content, content_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
        conn.commit()

    return len(rows)


def ingest_hfj_pages():
    results = []
    for url in HFJ_PAGE_SOURCES:
        try:
            html = fetch_page_html(url)
            page_title, sections = parse_hfj_page(html, url)
            count = upsert_hfj_sections(sections)
            results.append(
                {
                    "url": url,
                    "page_title": page_title,
                    "chunks_ingested": count,
                    "status": "ok",
                }
            )
        except Exception as e:
            results.append(
                {
                    "url": url,
                    "status": "error",
                    "error": str(e),
                }
            )
    return results


@app.on_event("startup")
def startup_event():
    init_db()
    ingest_hfj_pages()


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


def score_chunk(query: str, title: str, heading: str | None, content: str) -> float:
    query_terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
    if not query_terms:
        return 0.0

    haystacks = [
        (title or "").lower(),
        (heading or "").lower(),
        (content or "").lower(),
    ]

    score = 0.0
    for term in query_terms:
        if term in haystacks[0]:
            score += 4.0
        if term in haystacks[1]:
            score += 3.0
        if term in haystacks[2]:
            score += 1.0

    # exact useful phrases
    exact_phrases = [
        "human trafficking",
        "spot the signs",
        "warning signs",
        "get help",
        "forced labour",
        "sex trafficking",
        "sexual exploitation",
    ]
    for phrase in exact_phrases:
        if phrase in query.lower() and (
            phrase in haystacks[0] or phrase in haystacks[1] or phrase in haystacks[2]
        ):
            score += 5.0

    return score


def find_match(query: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_url, page_title, section_heading, content
                FROM hfj_content_chunks
                """
            )
            rows = cur.fetchall()

    best_row = None
    best_score = 0.0

    for row in rows:
        score = score_chunk(query, row[1], row[2], row[3])
        if score > best_score:
            best_score = score
            best_row = row

    if not best_row or best_score < 2.0:
        return None

    return {
        "source": best_row[0],
        "title": best_row[1],
        "section_heading": best_row[2],
        "answer": best_row[3],
    }


def build_us_state_response(state_name: str):
    state_slug = slugify_state(state_name)
    state_page = f"https://humantraffickinghotline.org/en/statistics/{state_slug}"

    return {
        "reply": (
            f"If you are in {state_name}:\n\n"
            "• Call 911 if there is immediate danger\n"
            "• National Human Trafficking Hotline: 1-888-373-7888\n"
            "• Text: 233733\n"
            "• Live chat and online reporting are also available\n\n"
            f"I’ve also included the official {state_name} page and the local services directory."
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


def build_confirmation_prompt(candidate: dict, session_id: str):
    value = candidate["value"]
    label = "state" if candidate["kind"] == "state" else "country"
    return {
        "reply": f"Did you mean {value} as your {label}? Please reply yes or no.",
        "source": "https://hopeforjustice.org/get-help/",
        "type": "hfj",
        "title": f"Confirm {label}",
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
                    SELECT source_url, page_title, COUNT(*)
                    FROM hfj_content_chunks
                    GROUP BY source_url, page_title
                    ORDER BY page_title
                    """
                )
                rows = cur.fetchall()

        return {
            "pages": [
                {
                    "source_url": row[0],
                    "page_title": row[1],
                    "chunk_count": row[2],
                }
                for row in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/reingest-hfj")
def reingest_hfj():
    try:
        results = ingest_hfj_pages()
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
            "pending_candidate": None,
            "saved_location": None,
        },
    )

    if session["stage"] == "awaiting_location_confirmation":
        if is_yes(text):
            candidate = session.get("pending_candidate")
            session["stage"] = None
            session["pending_candidate"] = None
            session["saved_location"] = None

            if not candidate:
                return {
                    "reply": "Please tell me the country or state so I can guide you properly.",
                    "source": "https://hopeforjustice.org/get-help/",
                    "type": "hfj",
                    "title": "Location needed",
                    "session_id": session_id,
                }

            if candidate["kind"] == "state":
                result = build_us_state_response(candidate["value"])
            else:
                result = build_country_response(candidate["value"])

            result["session_id"] = session_id
            return result

        if is_no(text):
            session["stage"] = "awaiting_location"
            session["pending_candidate"] = None
            session["saved_location"] = None
            return {
                "reply": (
                    "Thanks. Please tell me the country or state more explicitly, "
                    "for example Minnesota, California, Ireland, Canada, Belgium, Vietnam, or the UK."
                ),
                "source": "https://hopeforjustice.org/get-help/",
                "type": "hfj",
                "title": "Location needed",
                "session_id": session_id,
            }

        return {
            "reply": "Please reply yes or no.",
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": "Location confirmation",
            "session_id": session_id,
        }

    if session["stage"] == "awaiting_danger":
        if is_yes(text):
            saved_location = session.get("saved_location")

            if saved_location:
                if saved_location["confidence"] == "high":
                    session["stage"] = None
                    session["pending_candidate"] = None
                    session["saved_location"] = None

                    if saved_location["kind"] == "state":
                        result = build_us_state_response(saved_location["value"])
                    else:
                        result = build_country_response(saved_location["value"])

                    result["session_id"] = session_id
                    result["reply"] = (
                        "If someone is in immediate danger, contact emergency services right away.\n\n"
                        + result["reply"]
                    )
                    return result

                session["stage"] = "awaiting_location_confirmation"
                session["pending_candidate"] = saved_location
                session["saved_location"] = None
                return {
                    "reply": (
                        "If someone is in immediate danger, contact emergency services right away.\n\n"
                        f"Did you mean {saved_location['value']} as your location? Please reply yes or no."
                    ),
                    "source": "https://hopeforjustice.org/get-help/",
                    "type": "hfj",
                    "title": "Confirm location",
                    "session_id": session_id,
                }

            session["stage"] = "awaiting_location"
            return {
                "reply": (
                    "If someone is in immediate danger, contact emergency services right away.\n\n"
                    "Please now tell me the country or state so I can show the most relevant support route."
                ),
                "source": "https://hopeforjustice.org/get-help/",
                "type": "hfj",
                "title": "Emergency support",
                "session_id": session_id,
            }

        if is_no(text):
            saved_location = session.get("saved_location")

            if saved_location:
                if saved_location["confidence"] == "high":
                    session["stage"] = None
                    session["pending_candidate"] = None
                    session["saved_location"] = None

                    if saved_location["kind"] == "state":
                        result = build_us_state_response(saved_location["value"])
                    else:
                        result = build_country_response(saved_location["value"])

                    result["session_id"] = session_id
                    return result

                session["stage"] = "awaiting_location_confirmation"
                session["pending_candidate"] = saved_location
                session["saved_location"] = None
                return build_confirmation_prompt(saved_location, session_id)

            session["stage"] = "awaiting_location"
            return {
                "reply": (
                    "Thank you. Please tell me the country or state, for example Minnesota, California, Ireland, Canada, Belgium, Vietnam, or the UK."
                ),
                "source": "https://hopeforjustice.org/get-help/",
                "type": "hfj",
                "title": "Location needed",
                "session_id": session_id,
            }

        return {
            "reply": "Please reply yes or no: is anyone in immediate danger right now?",
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": "Immediate danger check",
            "session_id": session_id,
        }

    if session["stage"] == "awaiting_location":
        location = detect_location(user_input, text)

        if location:
            if location["confidence"] == "high":
                session["stage"] = None
                session["pending_candidate"] = None
                session["saved_location"] = None

                if location["kind"] == "state":
                    result = build_us_state_response(location["value"])
                else:
                    result = build_country_response(location["value"])

                result["session_id"] = session_id
                return result

            session["stage"] = "awaiting_location_confirmation"
            session["pending_candidate"] = location
            session["saved_location"] = None
            return build_confirmation_prompt(location, session_id)

        return {
            "reply": (
                "Thank you. I may not have fully recognized that location.\n\n"
                "If there is immediate danger, contact local emergency services right away. "
                "You can also seek help from official local authorities or trusted organisations.\n\n"
                "I’ve included Hope for Justice help information below."
            ),
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": "General location guidance",
            "session_id": session_id,
        }

    location = detect_location(user_input, text)
    if location:
        if location["confidence"] == "high":
            if location["kind"] == "state":
                result = build_us_state_response(location["value"])
            else:
                result = build_country_response(location["value"])

            result["session_id"] = session_id
            return result

        session["stage"] = "awaiting_location_confirmation"
        session["pending_candidate"] = location
        session["saved_location"] = None
        return build_confirmation_prompt(location, session_id)

    if is_help_trigger(text):
        detected_location = detect_location(user_input, text)
        session["stage"] = "awaiting_danger"
        session["pending_candidate"] = None
        session["saved_location"] = detected_location

        if detected_location and detected_location["confidence"] == "high":
            location_line = f"I understand you may be in {detected_location['value']}.\n\n"
        elif detected_location:
            location_line = f"I may have picked up {detected_location['value']} as your location.\n\n"
        else:
            location_line = ""

        return {
            "reply": (
                "I’m sorry this may be happening.\n\n"
                f"{location_line}"
                "Is anyone in immediate danger right now? Please reply yes or no."
            ),
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": "Immediate danger check",
            "session_id": session_id,
        }

    match = find_match(text)
    if match:
        return {
            "reply": match["answer"],
            "source": match["source"],
            "type": "hfj",
            "title": match["title"],
            "section_heading": match["section_heading"],
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
