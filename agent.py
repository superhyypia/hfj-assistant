def is_low_visibility_signal(text: str) -> bool:
    text = text.lower().strip()

    phrases = [
        "my phone is monitored",
        "my phone is being monitored",
        "my phone is watched",
        "someone is watching my phone",
        "i can't talk",
        "i cant talk",
        "i cannot talk",
        "i can't speak",
        "i cant speak",
        "i cannot speak",
        "someone is watching me",
        "i am being watched",
        "i'm being watched",
        "i cannot call",
        "i can't call",
        "i cant call",
        "i cannot text",
        "i can't text",
        "i cant text",
        "i need to be discreet",
        "i need to be discreet",
        "mi teléfono está vigilado",
        "mi telefono esta vigilado",
        "no puedo hablar",
        "no puedo llamar",
        "no puedo enviar mensajes",
        "me están vigilando",
        "me estan vigilando",
    ]

    return any(p in text for p in phrases)


def assess_risk_level(
    is_help: bool,
    is_unknown_location: bool,
    is_low_visibility: bool,
    text: str,
) -> str:
    text = text.lower().strip()

    emergency_markers = [
        "immediate danger",
        "in danger",
        "unsafe",
        "trapped",
        "cannot leave",
        "can't leave",
        "being trafficked",
        "llama al 911",
        "peligro inmediato",
        "no puedo salir",
    ]

    if is_low_visibility:
        return "high"

    if is_help and any(m in text for m in emergency_markers):
        return "high"

    if is_unknown_location and is_help:
        return "high"

    if is_help:
        return "medium"

    return "low"


def infer_intent(
    text: str,
    is_help: bool,
    has_location: bool,
    retrieval_match: dict | None,
) -> str:
    text = text.lower().strip()

    if is_help:
        return "support"

    if any(x in text for x in ["report", "report trafficking", "report modern slavery"]):
        return "reporting"

    if any(x in text for x in ["hotline", "contact", "phone", "number", "call"]):
        return "hotline_lookup"

    if has_location and any(x in text for x in ["help", "support", "find help", "where can i find help"]):
        return "location_support"

    if retrieval_match:
        return "education"

    return "general"


def plan_next_actions(
    text: str,
    session: dict,
    has_location: bool,
    is_help: bool,
    is_unknown_location: bool,
    is_low_visibility: bool,
    retrieval_match: dict | None,
):
    risk_level = assess_risk_level(
        is_help=is_help,
        is_unknown_location=is_unknown_location,
        is_low_visibility=is_low_visibility,
        text=text,
    )

    intent = infer_intent(
        text=text,
        is_help=is_help,
        has_location=has_location,
        retrieval_match=retrieval_match,
    )

    plan = {
        "risk_level": risk_level,
        "intent": intent,
        "actions": [],
        "response_mode": "standard",
    }

    if session.get("stage") == "awaiting_location":
        plan["intent"] = "support"

        if is_low_visibility:
            plan["actions"] = ["low_visibility_support"]
            plan["response_mode"] = "discreet"
            return plan

        if is_unknown_location:
            plan["actions"] = ["unknown_location_support"]
            plan["response_mode"] = "safety_first"
            return plan

        if has_location:
            plan["actions"] = ["route_support"]
            plan["response_mode"] = "official_first"
            return plan

        plan["actions"] = ["ask_location_again"]
        plan["response_mode"] = "safety_first"
        return plan

    if is_low_visibility:
        plan["actions"] = ["low_visibility_support"]
        plan["response_mode"] = "discreet"
        return plan

    if is_help:
        plan["intent"] = "support"

        if has_location:
            plan["actions"] = ["route_support"]
            plan["response_mode"] = "official_first"
        else:
            plan["actions"] = ["ask_location"]
            plan["response_mode"] = "safety_first"

        return plan

    if retrieval_match:
        confidence = retrieval_match.get("confidence", "low")

        if confidence == "high":
            plan["actions"] = ["answer_from_retrieval"]
            plan["response_mode"] = "grounded"
            return plan

        if confidence == "medium":
            plan["actions"] = ["answer_with_polish"]
            plan["response_mode"] = "grounded"
            return plan

    plan["actions"] = ["fallback_general"]
    plan["response_mode"] = "fallback"
    return plan
