import re
import pycountry

SESSION_STATE = {}

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
        "hola", "ayuda", "trata", "tráfico", "trafico", "explotación", "explotacion",
        "señales", "senales", "qué", "que es", "necesito", "peligro", "víctima", "victima",
        "dónde", "donde", "españa", "méxico", "mexico", "argentina", "colombia", "perú",
        "peru", "chile", "quiero ayuda", "estoy en", "puedo encontrar ayuda",
        "señales de explotación", "signos de explotación"
    ]
    lowered = text.lower()
    return "es" if any(marker in lowered for marker in spanish_markers) else "en"


def localize_text(key: str, language: str = "en", **kwargs) -> str:
    strings = {
        "danger_footer": {
            "en": "If someone may be in danger, please seek help from official services immediately.",
            "es": "Si alguien puede estar en peligro, por favor busca ayuda de los servicios oficiales de inmediato.",
        },
    }
    template = strings.get(key, {}).get(language) or strings.get(key, {}).get("en", "")
    return template.format(**kwargs)


def add_safety_footer(text: str, language: str = "en") -> str:
    return text.strip() + "\n\n" + localize_text("danger_footer", language)


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
        "i need help", "help me", "i think i am being trafficked", "i think i'm being trafficked",
        "i am being trafficked", "i'm being trafficked", "someone is being controlled",
        "someone is being exploited", "i think this is trafficking", "report trafficking",
        "i am trapped", "i'm trapped", "i cannot leave", "i can't leave",
        "someone cannot leave", "someone can't leave", "necesito ayuda", "ayúdame",
        "ayudame", "creo que estoy siendo víctima de trata", "creo que estoy siendo victima de trata",
        "estoy siendo explotado", "estoy siendo explotada", "no puedo salir",
        "alguien no puede salir",
    ]
    return any(t in text for t in triggers)


def looks_like_general_question(text: str) -> bool:
    triggers = [
        "what is", "what's", "how do i spot", "spot the signs", "signs of trafficking",
        "what are the signs", "what are signs of", "human trafficking", "labour trafficking",
        "labor trafficking", "sex trafficking", "sexual exploitation", "forced sexual exploitation",
        "signs of exploitation", "sexual exploitation signs", "forced labour", "forced labor",
        "define trafficking", "meaning of trafficking", "warning signs", "indicators of trafficking",
        "indicators of exploitation", "how to identify trafficking", "grooming signs",
        "qué es", "que es", "señales de", "senales de", "qué señales", "que señales",
        "signos de explotación", "explotación sexual", "explotacion sexual", "trata de personas",
        "qué es la trata", "que es la trata",
    ]
    return any(t in text for t in triggers)


def detect_us_state(text: str, original: str) -> dict | None:
    import re

    # Full state names
    for key, value in US_STATES.items():
        if re.search(rf"\b{re.escape(key)}\b", text):
            return {"kind": "state", "value": value, "confidence": "high"}

    # State abbreviations, but ignore common English words
    tokens = re.findall(r"\b[A-Z]{2}\b", original)

    for token in tokens:
        token_lower = token.lower()

        if token_lower in {"in", "on", "at", "by", "to", "of", "it", "is"}:
            continue

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
                return {"kind": "country", "value": country.name, "confidence": "high"}

    try:
        result = pycountry.countries.search_fuzzy(user_input.strip())
        if result:
            return {"kind": "country", "value": result[0].name, "confidence": "medium"}
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
