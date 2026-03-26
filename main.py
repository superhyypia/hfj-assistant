from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid
import re
import json
import pycountry
import psycopg
from openai import OpenAI

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


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


HFJ_KNOWLEDGE = [
    {
        "title": "What is human trafficking?",
        "source": "https://hopeforjustice.org/human-trafficking/",
        "keywords": [
            "what is human trafficking",
            "what is trafficking",
            "define trafficking",
            "human trafficking meaning",
        ],
        "answer": (
            "Human trafficking is the exploitation of another person for labour, "
            "services, or commercial sex through force, fraud, or coercion.\n\n"
            "It is not just about movement — the key issue is exploitation."
        ),
    },
    {
        "title": "Spot the signs",
        "source": "https://hopeforjustice.org/spot-the-signs/",
        "keywords": [
            "spot the signs",
            "warning signs",
            "how do i spot",
            "signs of trafficking",
        ],
        "answer": (
            "Common warning signs include:\n\n"
            "• Fear, anxiety, or inability to speak freely\n"
            "• Someone else controlling documents or movement\n"
            "• Poor living conditions or lack of pay\n"
            "• Dependency on another person\n\n"
            "Signs vary depending on the type of exploitation."
        ),
    },
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


def get_db_connection():
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(database_url)


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

            cur.execute("SELECT COUNT(*) FROM hfj_support_routes")
            count = cur.fetchone()[0]

            if count == 0:
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
                    ],
                )
        conn.commit()


@app.on_event("startup")
def startup_event():
    init_db()


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


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def find_match(text: str):
    best = None
    best_score = 0
    for item in HFJ_KNOWLEDGE:
        score = sum(1 for kw in item["keywords"] if kw in text)
        if score > best_score:
            best_score = score
            best = item
    return best if best_score > 0 else None


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

    library_country = detect_country_with_library(user_input)
    if library_country:
        return library_country

    return None


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


@app.post("/chat")
def chat(req: ChatRequest):
    user_input = req.message.strip()
    text = normalize(user_input)
    session_id = req.session_id or str(uuid.uuid4())

    if not user_input:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Very simple test use of DB-backed support routing
    location = detect_location(user_input, text)
    if location and location["kind"] == "country":
        country_name = location["value"].lower()

        if country_name == "ireland":
            route = get_support_route("ireland")
            if route:
                return {
                    "reply": (
                        f"If you are in {route['display_name']}:\n\n"
                        f"• {route['emergency_text']}\n"
                        f"• Support contact: {route['phone']}\n"
                        f"• Website: {route['website']}"
                    ),
                    "source": route["website"],
                    "type": "hfj",
                    "title": f"Support in {route['display_name']}",
                    "session_id": session_id,
                }

        if country_name in ["united kingdom", "great britain", "england", "scotland", "wales", "northern ireland"]:
            route = get_support_route("uk")
            if route:
                return {
                    "reply": (
                        f"If you are in {route['display_name']}:\n\n"
                        f"• {route['emergency_text']}\n"
                        f"• Support contact: {route['phone']}\n"
                        f"• Website: {route['website']}"
                    ),
                    "source": route["website"],
                    "type": "hfj",
                    "title": f"Support in {route['display_name']}",
                    "session_id": session_id,
                }

        if country_name in ["united states", "united states of america"]:
            route = get_support_route("united_states")
            if route:
                return {
                    "reply": (
                        f"If you are in {route['display_name']}:\n\n"
                        f"• {route['emergency_text']}\n"
                        f"• National Human Trafficking Hotline: {route['phone']}\n"
                        f"• Website: {route['website']}"
                    ),
                    "source": route["website"],
                    "type": "hfj",
                    "title": f"Support in {route['display_name']}",
                    "session_id": session_id,
                }

    match = find_match(text)
    if match:
        return {
            "reply": match["answer"],
            "source": match["source"],
            "type": "hfj",
            "title": match["title"],
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
