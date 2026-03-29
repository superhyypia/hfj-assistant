import json
import re
from typing import Optional

from ai import embed_texts
from db import get_db_connection


# ---------------------------
# Similarity
# ---------------------------
def cosine_similarity(a, b):
    if not a or not b or len(a) != len(b):
        return -1.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return -1.0

    return dot / (norm_a * norm_b)


# ---------------------------
# Intent detection
# ---------------------------
def detect_intent(query: str) -> str:
    q = query.lower()

    if any(x in q for x in ["what is", "define", "definition", "meaning"]):
        return "definition"

    if any(x in q for x in ["call", "number", "phone", "contact", "helpline"]):
        return "phone"

    if any(x in q for x in ["sign", "spot", "indicator"]):
        return "signs"

    if any(x in q for x in ["recruit", "tactic", "method"]):
        return "tactics"

    if any(x in q for x in ["how do", "what should", "report", "help"]):
        return "steps"

    return "general"


# ---------------------------
# Clean text
# ---------------------------
def clean_text(text: str, max_len=260):
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


# ---------------------------
# Format answer (SAFE)
# ---------------------------
def format_answer(answer: str, intent: str):
    """
    IMPORTANT:
    - Formatting must NEVER override intent
    - Especially: definition must NEVER become phone
    """

    text = clean_text(answer)

    # ✅ Definition ALWAYS wins
    if intent == "definition":
        return text

    # Phone formatting ONLY for phone intent
    if intent == "phone":
        match = re.search(r"\+?\d[\d\s\-]{6,}", text)
        if match:
            return f"The contact number is {match.group(0)}."

    return text


# ---------------------------
# Main retrieval
# ---------------------------
def find_match(query: str, user_region: str | None = None, language: str = "en"):

    intent = detect_intent(query)
    query_embedding = embed_texts([query])[0]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    content,
                    embedding_json,
                    source_url,
                    page_title,
                    section_heading,
                    source_site,
                    region,
                    source_name,
                    source_domain
                FROM hfj_content_chunks
                """
            )
            rows = cur.fetchall()

    best = None
    best_score = -1

    for row in rows:
        content = row[0] or ""
        embedding_json = row[1]

        if not embedding_json:
            continue

        try:
            embedding = json.loads(embedding_json)
        except:
            continue

        score = cosine_similarity(query_embedding, embedding)

        content_l = content.lower()
        heading_l = (row[4] or "").lower()
        title_l = (row[3] or "").lower()

        # ---------------------------
        # Keyword boost
        # ---------------------------
        for word in re.findall(r"\w+", query.lower()):
            if len(word) > 3:
                if word in heading_l:
                    score += 0.2
                elif word in title_l:
                    score += 0.1
                elif word in content_l:
                    score += 0.05

        # ---------------------------
        # Intent-aware scoring
        # ---------------------------

        if intent == "definition":
            if "what is" in heading_l:
                score += 1.2
            if "definition" in heading_l:
                score += 1.2

            # 🚫 penalise phone-heavy chunks
            if re.search(r"\d{3,}", content):
                score -= 0.6

        if intent == "phone":
            if re.search(r"\d{3,}", content):
                score += 0.8

        if intent == "steps":
            if "report" in heading_l or "contact" in heading_l:
                score += 0.8

        if intent == "tactics":
            if "recruit" in heading_l:
                score += 1.0

        if intent == "signs":
            if "sign" in heading_l:
                score += 1.0

        # ---------------------------
        # Region boost
        # ---------------------------
        if user_region and row[6] == user_region:
            score += 0.3

        if score > best_score:
            best_score = score
            best = {
                "answer": content,
                "source": row[2],
                "title": row[3],
                "section_heading": row[4],
                "source_site": row[5],
                "source_name": row[7],
                "source_domain": row[8],
                "confidence": round(score, 3),
                "score": round(score, 3),
            }

    if not best or best_score < 0.7:
        return None

    best["answer"] = format_answer(best["answer"], intent)

    return best
