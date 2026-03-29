import re


def is_low_visibility_signal(text: str) -> bool:
    """
    Detect softer, indirect concern signals where the user may be worried
    but is not explicitly asking for help yet.
    """
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
    """
    Very lightweight risk classification used for planning only.
    """
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


def _looks_like_definition_query(q: str) -> bool:
    return (
        q.startswith("what is ")
        or q.startswith("define ")
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
        r"\bhotline\b",
        r"\bhelpline\b",
        r"\bcontact number\b",
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

    # ---------------------------
    # 1. Strong definition / knowledge intent
    # ---------------------------
    if _looks_like_definition_query(q):
        if retrieval_match:
            return {
                "actions": ["answer_from_retrieval"],
                "reason": "definition query",
            }
        return {
            "actions": ["answer_with_llm"],
            "reason": "definition query without retrieval match",
        }

    # ---------------------------
    # 2. Assess risk
    # ---------------------------
    risk_level = assess_risk_level(
        is_help=is_help,
        is_unknown_location=is_unknown_location,
        is_low_visibility=is_low_visibility,
        text=text,
    )

    # ---------------------------
    # 3. Unknown-location support
    # ---------------------------
    if is_unknown_location:
        return {
            "actions": ["unknown_location_support"],
            "reason": "user does not know their location",
            "risk_level": risk_level,
        }

    # ---------------------------
    # 4. Low-visibility / indirect concern
    # ---------------------------
    if is_low_visibility and not is_help:
        return {
            "actions": ["low_visibility_support"],
            "reason": "indirect concern signal",
            "risk_level": risk_level,
        }

    # ---------------------------
    # 5. Direct support / reporting / contact routing
    # ---------------------------
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

    # ---------------------------
    # 6. Strong retrieval for knowledge queries
    # ---------------------------
    if retrieval_match and retrieval_match.get("score", 0) >= 0.68:
        return {
            "actions": ["answer_from_retrieval"],
            "reason": "strong retrieval match",
            "risk_level": risk_level,
        }

    # ---------------------------
    # 7. Weak retrieval can still be polished if available
    # ---------------------------
    if retrieval_match:
        return {
            "actions": ["answer_with_polish"],
            "reason": "weak retrieval match",
            "risk_level": risk_level,
        }

    # ---------------------------
    # 8. Final fallback
    # ---------------------------
    return {
        "actions": ["answer_with_llm"],
        "reason": "fallback",
        "risk_level": risk_level,
    }
