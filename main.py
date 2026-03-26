from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid
import re
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
    {
        "title": "Labour trafficking",
        "source": "https://hopeforjustice.org/human-trafficking/",
        "keywords": [
            "labour trafficking",
            "labor trafficking",
            "forced labour",
            "forced labor",
        ],
        "answer": (
            "Labour trafficking involves exploitation through work.\n\n"
            "It may include low pay, threats, long hours, poor conditions, and restricted movement."
        ),
    },
    {
        "title": "Sex trafficking",
        "source": "https://hopeforjustice.org/human-trafficking/",
        "keywords": [
            "sex trafficking",
            "sexual exploitation",
        ],
        "answer": (
            "Sex trafficking involves exploitation for commercial sex through force, fraud, or coercion.\n\n"
            "It may involve control, threats, or manipulation."
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
