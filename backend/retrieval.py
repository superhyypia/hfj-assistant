import json
import re
from typing import Optional

from ai import embed_texts
from db import get_db_connection


def cosine_similarity(a, b):
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return -1.0
    return dot / (norm_a * norm_b)


def detect_intent(query: str) -> str:
    q = query.lower()

    if any(x in q for x in [
        "phone", "number", "hotline", "helpline", "call", "contact"
    ]):
        return "phone"

    if "sign" in q:
        return "signs"

    if "recruit" in q or "tactic" in q:
        return "tactics"

    if any(x in q for x in ["what is", "define", "meaning"]):
        return "definition"

    return "general"


def extract_phone(text: str) -> Optional[str]:
    match = re.search(r"\b\d{3,4}[\s-]?\d{3}[\s-]?\d{3}\b", text)
    return match.group(0) if match else None


def _country_aliases():
    return {
        "ireland": ["ireland", "irish"],
        "uk": ["uk", "united kingdom", "britain"],
        "united_states": ["usa", "united states", "america"],
        "canada": ["canada"],
        "denmark": ["denmark", "danish"],
        "mexico": ["mexico"],
    }


def _extract_requested_country(query_l: str) -> str | None:
    aliases = _country_aliases()
    for country, terms in aliases.items():
        if any(term in query_l for term in terms):
            return country
    return None


def _mentions_country(text: str, country: str) -> bool:
    aliases = _country_aliases()
    return any(term in text for term in aliases.get(country, []))


def format_answer(answer: str, intent: str, query: str) -> str:
    if intent == "phone":
        phone = extract_phone(answer)
        if phone:
            if "garda" in query.lower():
                return f"The Garda Confidential Line is {phone}."
            return f"The contact number is {phone}."
    return answer.strip()


def find_match(query: str, user_region: str | None = None, language: str = "en"):
    intent = detect_intent(query)
    query_l = query.lower()
    requested_country = _extract_requested_country(query_l)

    query_embedding = embed_texts([query])[0]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT content, embedding_json, source_url, page_title,
                       section_heading, source_site, region, source_name, source_domain
                FROM hfj_content_chunks
            """)
            rows = cur.fetchall()

    best = None
    best_score = -1.0

    for row in rows:
        content = row[0] or ""
        embedding_json = row[1]
        source_url = row[2]
        page_title = row[3] or ""
        section_heading = row[4] or ""
        source_site = row[5] or ""
        region = row[6]
        source_name = row[7]
        source_domain = row[8]

        if not embedding_json:
            continue

        try:
            embedding = json.loads(embedding_json)
        except Exception:
            continue

        content_l = content.lower()
        title_l = page_title.lower()
        heading_l = section_heading.lower()

        # 🚨 HARD SAFETY FILTER
        if intent == "phone" and requested_country:
            mentions = (
                _mentions_country(content_l, requested_country)
                or _mentions_country(title_l, requested_country)
                or _mentions_country(heading_l, requested_country)
            )

            if region != requested_country and not mentions:
                continue  # ← THIS IS THE KEY FIX

        score = cosine_similarity(query_embedding, embedding)

        if intent == "phone":
            if extract_phone(content):
                score += 1.5
            if region == requested_country:
                score += 2.0

        if score > best_score:
            best_score = score
            best = {
                "answer": content,
                "source": source_url,
                "title": page_title,
                "section_heading": section_heading,
                "source_site": source_site,
                "source_name": source_name,
                "source_domain": source_domain,
                "region": region,
                "score": round(score, 3),
            }

    if not best:
        return None

    best["answer"] = format_answer(best["answer"], intent, query)
    return best
