def decide_next_step(
    text: str,
    session: dict,
    has_location: bool,
    is_help: bool,
    is_unknown_location: bool,
    retrieval_match: dict | None,
):
    if session.get("stage") == "awaiting_location":
        if is_unknown_location:
            return "unknown_location_support"

        if has_location:
            return "route_support"

        return "ask_location_again"

    if is_help:
        if has_location:
            return "route_support"
        return "ask_location"

    if retrieval_match:
        confidence = retrieval_match.get("confidence")

        if confidence == "high":
            return "answer_from_retrieval"

        if confidence == "medium":
            return "answer_with_polish"

        return "fallback_general"

    return "fallback_general"
