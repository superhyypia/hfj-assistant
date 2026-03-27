from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

import os
import uuid
import re
import json
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

USER_AGENT = "Mozilla/5.0 (compatible; HFJ-Assistant-MVP/1.3)"

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
    language: str | None = None


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


def clean_answer_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def detect_language(text: str) -> str:
    spanish_markers = [
        "hola",
        "ayuda",
        "trata",
        "tráfico",
        "trafico",
        "explotación",
        "explotacion",
        "señales",
        "senales",
        "qué",
        "que es",
        "necesito",
        "peligro",
        "víctima",
        "victima",
        "dónde",
        "donde",
        "españa",
        "méxico",
        "mexico",
        "argentina",
        "colombia",
        "perú",
        "peru",
        "chile",
        "quiero ayuda",
        "estoy en",
        "puedo encontrar ayuda",
        "señales de explotación",
        "signos de explotación",
    ]

    lowered = text.lower()
    if any(marker in lowered for marker in spanish_markers):
        return "es"
    return "en"


def localize_text(key: str, language: str = "en", **kwargs) -> str:
    strings = {
        "location_needed": {
            "en": "Please tell me your country or state so I can give you the right support options.",
            "es": "Por favor, dime tu país o estado para poder darte las opciones de apoyo adecuadas.",
        },
        "danger_footer": {
            "en": "If someone may be in danger, please seek help from official services immediately.",
            "es": "Si alguien puede estar en peligro, por favor busca ayuda de los servicios oficiales de inmediato.",
        },
        "support_in_country": {
            "en": "If you are in {country}:",
            "es": "Si estás en {country}:",
        },
        "support_in_state": {
            "en": "If you are in {state}:",
            "es": "Si estás en {state}:",
        },
        "immediate_support": {
            "en": (
                "I’m really sorry this may be happening.\n\n"
                "If there is immediate danger, contact emergency services now.\n\n"
                "Please tell me your country or state and I’ll give you the right support options."
            ),
            "es": (
                "Siento mucho que esto pueda estar ocurriendo.\n\n"
                "Si hay peligro inmediato, contacta ahora con los servicios de emergencia.\n\n"
                "Por favor, dime tu país o estado y te daré las opciones de apoyo adecuadas."
            ),
        },
        "immediate_support_with_location": {
            "en": (
                "I’m really sorry this may be happening.\n\n"
                "If there is immediate danger, contact emergency services now.\n\n"
                "I understand you may be in {location}. If that is right, I can guide you to support options for that location."
            ),
            "es": (
                "Siento mucho que esto pueda estar ocurriendo.\n\n"
                "Si hay peligro inmediato, contacta ahora con los servicios de emergencia.\n\n"
                "Entiendo que puedes estar en {location}. Si es así, puedo orientarte hacia opciones de apoyo para ese lugar."
            ),
        },
        "generic_unknown_country": {
            "en": (
                "• If there is immediate danger, contact local emergency services right away\n"
                "• Seek help from official local authorities or trusted local support organisations\n\n"
                "I’ve included Hope for Justice help information below while you seek the appropriate local official support."
            ),
            "es": (
                "• Si hay peligro inmediato, contacta de inmediato con los servicios de emergencia locales\n"
                "• Busca ayuda de las autoridades locales oficiales o de organizaciones de apoyo de confianza\n\n"
                "He incluido la información de ayuda de Hope for Justice mientras buscas el apoyo oficial local adecuado."
            ),
        },
        "emergency_line_prefix": {
            "en": "• {text}",
            "es": "• {text}",
        },
        "support_contact_prefix": {
            "en": "• Support contact: {phone}",
            "es": "• Contacto de apoyo: {phone}",
        },
        "website_prefix": {
            "en": "• Website: {website}",
            "es": "• Sitio web: {website}",
        },
        "country_help_intro": {
            "en": "If you are in {country}:",
            "es": "Si estás en {country}:",
        },
        "state_help_intro": {
            "en": "If you are in {state}:",
            "es": "Si estás en {state}:",
        },
        "help_prompt_prefix": {
            "en": (
                "I’m really sorry this may be happening.\n\n"
                "If there is immediate danger, contact emergency services now.\n\n"
            ),
            "es": (
                "Siento mucho que esto pueda estar ocurriendo.\n\n"
                "Si hay peligro inmediato, contacta ahora con los servicios de emergencia.\n\n"
            ),
        },
    }

    template = strings.get(key, {}).get(language) or strings.get(key, {}).get("en", "")
    return template.format(**kwargs)


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
        "necesito ayuda",
        "ayúdame",
        "ayudame",
        "creo que estoy siendo víctima de trata",
        "creo que estoy siendo victima de trata",
        "estoy siendo explotado",
        "estoy siendo explotada",
        "no puedo salir",
        "alguien no puede salir",
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
        "what are signs of",
        "human trafficking",
        "labour trafficking",
        "labor trafficking",
        "sex trafficking",
        "sexual exploitation",
        "forced sexual exploitation",
        "signs of exploitation",
        "sexual exploitation signs",
        "forced labour",
        "forced labor",
        "define trafficking",
        "meaning of trafficking",
        "warning signs",
        "indicators of trafficking",
        "indicators of exploitation",
        "how to identify trafficking",
        "grooming signs",
        "qué es",
        "que es",
        "señales de",
        "senales de",
        "qué señales",
        "que señales",
        "signos de explotación",
        "explotación sexual",
        "explotacion sexual",
        "trata de personas",
        "qué es la trata",
        "que es la trata",
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


def infer_user_region(location: dict | None) -> str | None:
    if not location:
        return None
    if location["kind"] == "state":
        return "united_states"
    key = normalize_country_key(location["value"])
    if key in {"ireland", "uk", "united_states"}:
        return key
    return None


def add_safety_footer(text: str, language: str = "en") -> str:
    return text.strip() + "\n\n" + localize_text("danger_footer", language)


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
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(source_url, chunk_index)
                )
                """
            )

            cur.execute("""
                ALTER TABLE hfj_content_chunks
                ADD COLUMN IF NOT EXISTS source_site TEXT NOT NULL DEFAULT 'hopeforjustice'
            """)

            cur.execute("""
                ALTER TABLE hfj_content_chunks
                ADD COLUMN IF NOT EXISTS region TEXT NOT NULL DEFAULT 'global'
            """)

            cur.execute("""
                ALTER TABLE hfj_content_chunks
                ADD COLUMN IF NOT EXISTS content_type TEXT NOT NULL DEFAULT 'education'
            """)

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

            cur.execute("""
                ALTER TABLE ai_country_support_cache
                ADD COLUMN IF NOT EXISTS language TEXT NOT NULL DEFAULT 'en'
            """)

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
            cur.execute("DELETE FROM hfj_content_chunks WHERE source_url = %s", (source_url,))
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
    query_terms = [t for t in re.findall(r"[a-z0-9áéíóúñ]+", query.lower()) if len(t) > 2]
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
        "trata de personas",
        "explotación sexual",
        "explotacion sexual",
        "señales de trata",
        "senales de trata",
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

    if "help" in query_l or "ayuda" in query_l:
        if content_type == "support":
            score += 4.0

    if (
        "sign" in query_l
        or "what is" in query_l
        or "what are the signs" in query_l
        or "sexual exploitation" in query_l
        or "señales" in query_l
        or "senales" in query_l
        or "qué es" in query_l
        or "que es" in query_l
        or "explotación" in query_l
        or "explotacion" in query_l
    ) and content_type == "education":
        score += 3.0

    return score


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

    best_score, best_row = scored[0]
    selected_chunks = [best_row[6]]

    for score, row in scored[1:3]:
        same_section = row[5] == best_row[5]
        close_score = score >= best_score * 0.85
        if same_section and close_score:
            selected_chunks.append(row[6])

    combined = clean_answer_text("\n\n".join(selected_chunks))

    return {
        "source": best_row[0],
        "source_site": best_row[1],
        "region": best_row[2],
        "content_type": best_row[3],
        "title": best_row[4],
        "section_heading": best_row[5],
        "answer": combined[:1200],
    }


def get_ai_country_support(country_name: str, language: str = "en"):
    if not client:
        return None

    country_key = normalize_country_key(country_name)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload_json
                FROM ai_country_support_cache
                WHERE country_key = %s AND language = %s
                """,
                (country_key, language),
            )
            row = cur.fetchone()

    if row:
        try:
            return json.loads(row[0])
        except Exception:
            pass

    response_language = "Spanish" if language == "es" else "English"

    response = client.responses.create(
        model="gpt-4o",
        input=f"""
You are helping build a victim-support assistant.

Find official or highly credible anti-trafficking or victim-support contacts for {country_name}.

Return ONLY valid JSON in this exact schema:

{{
  "title": "{'Contactos locales adicionales para ' + country_name if language == 'es' else 'Additional local contacts for ' + country_name}",
  "status": "verify",
  "contacts": [
    {{
      "organisation": "",
      "phone": "",
      "hours": "",
      "website": "",
      "email": "",
      "notes": ""
    }}
  ]
}}

Rules:
- Prefer government agencies, national helplines, or major victim-support organisations
- Do not invent contact details
- If a field is unknown, use an empty string
- Include up to 3 contacts
- No markdown
- No explanation outside JSON
- Return all labels and notes in {response_language}
"""
    )

    raw = response.output_text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    if not raw:
        return None

    try:
        data = json.loads(raw)
    except Exception:
        data = {
            "title": (
                f"Contactos locales adicionales para {country_name}"
                if language == "es"
                else f"Additional local contacts for {country_name}"
            ),
            "status": "verify",
            "contacts": [],
            "raw_text": raw,
        }

    if "title" not in data:
        data["title"] = (
            f"Contactos locales adicionales para {country_name}"
            if language == "es"
            else f"Additional local contacts for {country_name}"
        )
    if "status" not in data:
        data["status"] = "verify"
    if "contacts" not in data or not isinstance(data["contacts"], list):
        data["contacts"] = []

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_country_support_cache (country_key, country_name, language, payload_json, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (country_key)
                DO UPDATE SET
                    country_name = EXCLUDED.country_name,
                    language = EXCLUDED.language,
                    payload_json = EXCLUDED.payload_json,
                    updated_at = NOW()
                """,
                (country_key, country_name, language, json.dumps(data)),
            )
        conn.commit()

    return data


def build_us_state_response(state_name: str, language: str = "en"):
    state_slug = slugify_state(state_name)
    state_page = f"https://humantraffickinghotline.org/en/statistics/{state_slug}"

    if language == "es":
        reply = (
            f"Si estás en {state_name}:\n\n"
            "• Si hay peligro inmediato, llama ahora al 911\n"
            "• Línea Nacional contra la Trata de Personas: 1-888-373-7888\n"
            "• Texto: 233733\n"
            "• También hay chat en vivo y notificación en línea\n\n"
            f"La Línea Nacional contra la Trata de Personas también tiene una página dedicada a {state_name}, "
            "y he incluido abajo el directorio de servicios locales."
        )
    else:
        reply = (
            f"If you are in {state_name}:\n\n"
            "• If there is immediate danger, call 911 now\n"
            "• National Human Trafficking Hotline: 1-888-373-7888\n"
            "• Text: 233733\n"
            "• Live chat and online reporting are also available\n\n"
            f"The National Human Trafficking Hotline also has a dedicated {state_name} page, "
            "and I’ve included the local services directory below."
        )

    return {
        "reply": reply,
        "source": state_page,
        "extra_sources": [
            "https://humantraffickinghotline.org/en/contact",
            "https://humantraffickinghotline.org/en/find-local-services",
        ],
        "type": "hfj",
        "title": f"Support in {state_name}" if language == "en" else f"Apoyo en {state_name}",
    }


def build_country_response(country_name: str, language: str = "en"):
    country_key = normalize_country_key(country_name)
    route = get_support_route(country_key)
    display_name = country_name.strip()

    if route:
        intro = localize_text("country_help_intro", language, country=route["display_name"])
        reply_lines = [intro, "", localize_text("emergency_line_prefix", language, text=route["emergency_text"])]

        if route["phone"]:
            reply_lines.append(localize_text("support_contact_prefix", language, phone=route["phone"]))

        if route["website"]:
            reply_lines.append(localize_text("website_prefix", language, website=route["website"]))

        result = {
            "reply": "\n".join(reply_lines),
            "source": route["website"] or "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": (f"Support in {route['display_name']}" if language == "en" else f"Apoyo en {route['display_name']}"),
        }

        is_thin_route = (
            not route.get("phone") and
            (
                not route.get("website")
                or route.get("website") == "https://hopeforjustice.org/get-help/"
            )
        )

        if is_thin_route:
            ai_contacts = get_ai_country_support(route["display_name"], language=language)
            if ai_contacts:
                result["additional_contacts_title"] = ai_contacts.get("title")
                result["additional_contacts_status"] = ai_contacts.get("status", "verify")
                result["additional_contacts"] = ai_contacts.get("contacts", [])
                result["additional_contacts_raw_text"] = ai_contacts.get("raw_text", "")

        return result

    result = {
        "reply": (
            localize_text("country_help_intro", language, country=display_name)
            + "\n\n"
            + localize_text("generic_unknown_country", language)
        ),
        "source": "https://hopeforjustice.org/get-help/",
        "type": "hfj",
        "title": (f"Support in {display_name}" if language == "en" else f"Apoyo en {display_name}"),
    }

    ai_contacts = get_ai_country_support(display_name, language=language)
    if ai_contacts:
        result["additional_contacts_title"] = ai_contacts.get("title")
        result["additional_contacts_status"] = ai_contacts.get("status", "verify")
        result["additional_contacts"] = ai_contacts.get("contacts", [])
        result["additional_contacts_raw_text"] = ai_contacts.get("raw_text", "")

    return result


def build_help_prompt(location: dict | None, session_id: str, language: str = "en"):
    if location and location["confidence"] == "high":
        return {
            "reply": localize_text("immediate_support_with_location", language, location=location["value"]),
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": "Immediate support" if language == "en" else "Apoyo inmediato",
            "session_id": session_id,
        }

    return {
        "reply": localize_text("immediate_support", language),
        "source": "https://hopeforjustice.org/get-help/",
        "type": "hfj",
        "title": "Immediate support" if language == "en" else "Apoyo inmediato",
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
    try:
        user_input = req.message.strip()
        text = normalize(user_input)

        if not user_input:
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        language = req.language if req.language in {"en", "es"} else detect_language(user_input)

        session_id = req.session_id or str(uuid.uuid4())
        session = SESSION_STATE.setdefault(
            session_id,
            {
                "stage": None,
                "saved_location": None,
                "language": language,
            },
        )

        session["language"] = language

        if session["stage"] == "awaiting_location" and looks_like_general_question(text):
            session["stage"] = None
            session["saved_location"] = None

        if session["stage"] == "awaiting_location":
            location = detect_location(user_input, text)

            if location:
                session["stage"] = None
                session["saved_location"] = None

                if location["kind"] == "state":
                    result = build_us_state_response(location["value"], language=language)
                else:
                    result = build_country_response(location["value"], language=language)

                result["session_id"] = session_id
                result["language"] = language
                return result

            return {
                "reply": localize_text("location_needed", language),
                "source": "https://hopeforjustice.org/get-help/",
                "type": "hfj",
                "title": "Location needed" if language == "en" else "Ubicación necesaria",
                "session_id": session_id,
                "language": language,
            }

        location = detect_location(user_input, text)
        if location:
            if location.get("kind") == "state":
                result = build_us_state_response(location["value"], language=language)
                result["session_id"] = session_id
                result["language"] = language
                return result

            if location.get("kind") == "country":
                result = build_country_response(location["value"], language=language)
                result["session_id"] = session_id
                result["language"] = language
                return result

        if looks_like_general_question(text):
            user_region = infer_user_region(location)
            match = find_match(text, user_region=user_region)
            if match:
                if language == "es" and client:
                    translation = client.responses.create(
                        model="gpt-4o",
                        input=f"""
Translate the following support information into Spanish.
Keep it clear, calm, and structured.
Do not add extra advice.

Text:
{match["answer"]}
"""
                    )
                    answer_text = translation.output_text.strip()
                else:
                    answer_text = match["answer"]

                return {
                    "reply": add_safety_footer(answer_text, language),
                    "source": match["source"],
                    "type": "hfj",
                    "title": match["title"],
                    "section_heading": match["section_heading"],
                    "source_site": match["source_site"],
                    "session_id": session_id,
                    "language": language,
                }

        if is_help_trigger(text):
            detected_location = detect_location(user_input, text)

            if detected_location and detected_location["confidence"] == "high":
                if detected_location["kind"] == "state":
                    result = build_us_state_response(detected_location["value"], language=language)
                else:
                    result = build_country_response(detected_location["value"], language=language)

                result["reply"] = localize_text("help_prompt_prefix", language) + result["reply"]
                result["session_id"] = session_id
                result["language"] = language
                return result

            session["stage"] = "awaiting_location"
            response = build_help_prompt(detected_location, session_id, language=language)
            response["language"] = language
            return response

        user_region = infer_user_region(location)
        match = find_match(text, user_region=user_region)
        if match:
            if language == "es" and client:
                translation = client.responses.create(
                    model="gpt-4o",
                    input=f"""
Translate the following support information into Spanish.
Keep it clear, calm, and structured.
Do not add extra advice.

Text:
{match["answer"]}
"""
                )
                answer_text = translation.output_text.strip()
            else:
                answer_text = match["answer"]

            return {
                "reply": add_safety_footer(answer_text, language),
                "source": match["source"],
                "type": "hfj",
                "title": match["title"],
                "section_heading": match["section_heading"],
                "source_site": match["source_site"],
                "session_id": session_id,
                "language": language,
            }

        if not client:
            raise HTTPException(status_code=500, detail="Missing API key")

        response = client.responses.create(
            model="gpt-4o",
            input=f"""
You are the Hope for Justice assistant.

Respond in {"Spanish" if language == "es" else "English"}.

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
            "title": "General guidance" if language == "en" else "Orientación general",
            "session_id": session_id,
            "language": language,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {type(e).__name__}: {str(e)}")
