from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid
import re
import json
import pycountry
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

# MVP in-memory session store
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


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


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
    ]
    return any(t in text for t in triggers)


def is_yes(text: str) -> bool:
    yes_words = ["yes", "yeah", "y", "urgent", "in danger", "immediate danger"]
    return any(word == text or word in text for word in yes_words)


def is_no(text: str) -> bool:
    no_words = ["no", "nope", "not right now", "not immediate", "safe for now"]
    return any(word == text or word in text for word in no_words)


def detect_us_state(text: str, original: str) -> dict | None:
    # High-confidence: full state name
    for key, value in US_STATES.items():
        if re.search(rf"\b{re.escape(key)}\b", text):
            return {"kind": "state", "value": value, "confidence": "high"}

    # Medium-confidence: only uppercase abbreviations from original user input
    # This avoids false positives like "in" -> Indiana or "or" -> Oregon
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

    # High-confidence: country name appears as a whole phrase in the input
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

    # Medium-confidence: fuzzy match for short inputs like "Canada" or "Vietnam"
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


def detect_country_with_openai(user_input: str) -> dict | None:
    if not client:
        return None

    try:
        response = client.responses.create(
            model="gpt-4o",
            input=f"""
Extract the country mentioned in this message.

Rules:
- Return JSON only.
- Format: {{"country": "<country name or null>"}}
- If there is no country, return {{"country": null}}.
- Do not return a U.S. state as a country.
- Be conservative. If unsure, return null.

Message: {user_input}
"""
        )
        raw = response.output_text.strip()
        data = json.loads(raw)
        country = data.get("country")
        if isinstance(country, str) and country.strip():
            return {
                "kind": "country",
                "value": country.strip(),
                "confidence": "medium",
            }
        return None
    except Exception:
        return None


def detect_location(user_input: str, text: str) -> dict | None:
    state_result = detect_us_state(text, user_input)
    if state_result:
        return state_result

    library_country = detect_country_with_library(user_input)
    if library_country:
        return library_country

    ai_country = detect_country_with_openai(user_input)
    if ai_country:
        return ai_country

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
    normalized = country_name.strip().lower()

    if normalized == "ireland":
        return {
            "reply": (
                "If you are in Ireland:\n\n"
                "• Call 112 or 999 if there is immediate danger\n"
                "• Use approved local authorities or support services\n\n"
                "I’ve included Hope for Justice help information below."
            ),
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": "Support in Ireland",
        }

    if normalized in [
        "united kingdom",
        "great britain",
        "england",
        "scotland",
        "wales",
        "northern ireland",
    ]:
        return {
            "reply": (
                "If you are in the UK:\n\n"
                "• Call 999 if there is immediate danger\n"
                "• Use approved local authorities or support services\n\n"
                "I’ve included Hope for Justice contact information below."
            ),
            "source": "https://hopeforjustice.org/contact/",
            "type": "hfj",
            "title": "Support in the UK",
        }

    if normalized in ["united states", "united states of america"]:
        return {
            "reply": (
                "If you are in the United States:\n\n"
                "• Call 911 if there is immediate danger\n"
                "• National Human Trafficking Hotline: 1-888-373-7888\n"
                "• Text: 233733\n"
                "• Live chat and online reporting are available\n\n"
                "If you tell me your state, I can make this more specific."
            ),
            "source": "https://humantraffickinghotline.org/en/contact",
            "extra_sources": [
                "https://humantraffickinghotline.org/en/find-local-services"
            ],
            "type": "hfj",
            "title": "Support in the United States",
        }

    # Safe global fallback
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
        },
    )

    # Confirmation stage
    if session["stage"] == "awaiting_location_confirmation":
        if is_yes(text):
            candidate = session.get("pending_candidate")
            session["stage"] = None
            session["pending_candidate"] = None

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
            return {
                "reply": (
                    "Thanks. Please tell me the country or state more explicitly, "
                    "for example Minnesota, California, Ireland, Canada, Vietnam, or the UK."
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

    # Help flow: danger check
    if session["stage"] == "awaiting_danger":
        if is_yes(text):
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
            session["stage"] = "awaiting_location"
            return {
                "reply": (
                    "Thank you. Please tell me the country or state, for example Minnesota, California, Ireland, Canada, Vietnam, or the UK."
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

    # Help flow: awaiting location
    if session["stage"] == "awaiting_location":
        location = detect_location(user_input, text)

        if location:
            if location["confidence"] == "high":
                session["stage"] = None
                session["pending_candidate"] = None

                if location["kind"] == "state":
                    result = build_us_state_response(location["value"])
                else:
                    result = build_country_response(location["value"])

                result["session_id"] = session_id
                return result

            session["stage"] = "awaiting_location_confirmation"
            session["pending_candidate"] = location
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

    # Direct location handling outside help flow
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
        return build_confirmation_prompt(location, session_id)

    # Start guided help flow
    if is_help_trigger(text):
        session["stage"] = "awaiting_danger"
        session["pending_candidate"] = None
        return {
            "reply": (
                "I’m sorry this may be happening.\n\n"
                "Is anyone in immediate danger right now? Please reply yes or no."
            ),
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": "Immediate danger check",
            "session_id": session_id,
        }

    # Mini-RAG
    match = find_match(text)
    if match:
        return {
            "reply": match["answer"],
            "source": match["source"],
            "type": "hfj",
            "title": match["title"],
            "session_id": session_id,
        }

    # OpenAI fallback
    if not client:
        raise HTTPException(status_code=500, detail="Missing API key")

    try:
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
