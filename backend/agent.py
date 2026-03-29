import re


def is_low_visibility_signal(text: str) -> bool:
    if not text:
        return False

    t = text.lower().strip()

    patterns = [
        "i'm worried",
        "im worried",
        "i am worried",
        "concerned about",
        "something feels wrong",
        "this feels wrong",
        "not sure if",
        "might be trafficked",
        "may be trafficked",
        "someone might be in danger",
        "someone may be in danger",
        "i think something is wrong",
        "i'm not sure",
        "im not sure",
        "warning signs",
        "signs of trafficking",
    ]

    return any(pattern in t for pattern in patterns)


def assess_risk_level(
    is_help: bool,
    is_unknown_location: bool,
    is_low_visibility: bool,
    text: str,
) -> str:
    t = (text or "").lower()

    urgent_terms = [
        "immediate danger",
        "in danger now",
        "right now",
        "urgent",
        "emergency",
        "help now",
        "call police",
        "being hurt",
        "locked up",
        "trapped",
        "unsafe",
    ]

    if any(term in t for term in urgent_terms):
        return "high"

    if is_help or is_unknown_location:
        return "medium"

    if is_low_visibility:
        return "low"

    return "info"


def _looks_like_phone_query(q: str) -> bool:
    patterns = [
        r"\bphone number\b",
        r"\bcontact number\b",
        r"\bwhat number\b",
        r"\bwhat is the number\b",
        r"\bhotline\b",
        r"\bhelpline\b",
        r"\bconfidential line\b",
        r"\bnumber to call\b",
        r"\bcall number\b",
        r"\bwhat is .* number\b",
        r"\bwhat is .* line\b",
    ]
    return any(re.search(pattern, q) for pattern in patterns)


def _looks_like_signs_query(q: str) -> bool:
    patterns = [
        r"\bsigns of\b",
        r"\bwhat are the signs\b",
        r"\bspot the signs\b",
        r"\bindicators\b",
        r"\bwarning signs\b",
    ]
    return any(re.search(pattern, q) for pattern in patterns)


def _looks_like_tactics_query(q: str) -> bool:
    patterns = [
        r"\brecruit\b",
        r"\brecruitment\b",
        r"\btactics\b",
        r"\bmethods\b",
        r"\bhow do traffickers recruit\b",
    ]
    return any(re.search(pattern, q) for pattern in patterns)


def _looks_like_definition_query(q: str) -> bool:
    return (
        q.startswith("define ")
        or q.startswith("what is ")
        or q.startswith("what are ")
        or q.startswith("explain ")
    )


def _looks_like_support_contact_query(q: str) -> bool:
    support_patterns = [
        r"\bwho do i call\b",
        r"\bwho can i call\b",
        r"\bwho should i call\b",
        r"\bwho do i contact\b",
        r"\bwho can i contact\b",
        r"\bwho should i contact\b",
        r"\bhow do i report\b",
        r"\breport trafficking\b",
        r"\bneed help\b",
        r"\bi need help\b",
        r"\bget help\b",
        r"\bi am being trafficked\b",
        r"\bi think i am being trafficked\b",
        r"\bi am in danger\b",
    ]
    return any(re.search(pattern, q) for pattern in support_patterns)


def plan_next_actions(
    text: str,
    session: dict,
    has_location: bool,
    is_help: bool,
    is_unknown_location: bool,
    is_low_visibility: bool,
    retrieval_match: dict | None,
):
    q = (text or "").lower().strip()

    risk_level = assess_risk_level(
        is_help=is_help,
        is_unknown_location=is_unknown_location,
        is_low_visibility=is_low_visibility,
        text=text,
    )

    if is_unknown_location:
        return {
            "actions": ["unknown_location_support"],
            "reason": "user does not know their location",
            "risk_level": risk_level,
        }

    if is_low_visibility and not is_help:
        return {
            "actions": ["low_visibility_support"],
            "reason": "indirect concern signal",
            "risk_level": risk_level,
        }

    # HELP / SUPPORT: never fall back to general AI
    if is_help or _looks_like_support_contact_query(q):
        if has_location or session.get("saved_location"):
            return {
                "actions": ["route_support"],
                "reason": "support request with location",
                "risk_level": risk_level,
            }
        return {
            "actions": ["ask_location"],
            "reason": "support request without location",
            "risk_level": risk_level,
        }

    # FACTUAL CONTACT LOOKUP: retrieval first, AI fallback allowed
    if _looks_like_phone_query(q):
        if retrieval_match:
            return {
                "actions": ["answer_from_retrieval"],
                "reason": "phone query",
                "risk_level": risk_level,
            }
        return {
            "actions": ["answer_with_llm"],
            "reason": "phone query without retrieval match",
            "risk_level": risk_level,
        }

    if _looks_like_signs_query(q):
        if retrieval_match:
            return {
                "actions": ["answer_from_retrieval"],
                "reason": "signs query",
                "risk_level": risk_level,
            }
        return {
            "actions": ["answer_with_llm"],
            "reason": "signs query without retrieval match",
            "risk_level": risk_level,
        }

    if _looks_like_tactics_query(q):
        if retrieval_match:
            return {
                "actions": ["answer_from_retrieval"],
                "reason": "tactics query",
                "risk_level": risk_level,
            }
        return {
            "actions": ["answer_with_llm"],
            "reason": "tactics query without retrieval match",
            "risk_level": risk_level,
        }

    if _looks_like_definition_query(q):
        if retrieval_match:
            return {
                "actions": ["answer_from_retrieval"],
                "reason": "definition query",
                "risk_level": risk_level,
            }
        return {
            "actions": ["answer_with_llm"],
            "reason": "definition query without retrieval match",
            "risk_level": risk_level,
        }

    if retrieval_match:
        return {
            "actions": ["answer_with_polish"],
            "reason": "strong retrieval match",
            "risk_level": risk_level,
        }

    return {
        "actions": ["answer_with_llm"],
        "reason": "fallback",
        "risk_level": risk_level,
    }
