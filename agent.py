def decide_next_step(
    text: str,
    session: dict,
    has_location: bool,
    is_help: bool,
    is_unknown_location: bool,
    retrieval_match: dict | None,
):
    """
    Returns a decision string for what the system should do next.
    """

    # 1. Already in location flow
    if session.get("stage") == "awaiting_location":
        if is_unknown_location:
            return "unknown_location_support"

        if has_location:
            return "route_support"

        return "ask_location_again"

    # 2. Strong help / distress signal
    if is_help:
        if has_location:
            return "route_support"
        else:
            return "ask_location"

    # 3. Good retrieval result
    if retrieval_match:
        confidence = retrieval_match.get("confidence")

        if confidence == "high":
            return "answer_from_retrieval"

        if confidence == "medium":
            return "answer_with_polish"

        return "fallback_general"

    # 4. Nothing matched
    return "fallback_general"
