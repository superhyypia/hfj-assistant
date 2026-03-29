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

    if any(x in q for x in ["phone number", "contact number", "what number", "what is the number", "hotline", "helpline", "confidential line", "number to call", "call number"]):
        return "phone"

    if any(x in q for x in ["signs of", "what are the signs", "spot the signs", "indicators", "warning signs"]):
        return "signs"

    if any(x in q for x in ["recruit", "recruitment", "tactics", "methods", "how do traffickers recruit"]):
        return "tactics"

    if any(x in q for x in ["what is", "define", "definition", "meaning", "explain"]):
        return "definition"

    if any(x in q for x in ["how do", "what should", "report", "help"]):
        return "steps"

    return "general"


def clean_text(text: str, max_len: int = 320) -> str:
    return re.sub(r"\s+", " ", text).strip()[:max_len]


def extract_phone(text: str) -> Optional[str]:
    match = re.search(r"\b\d{3,4}[\s-]?\d{3}[\s-]?\d{3}\b", text)
    return match.group(0) if match else None


def format_answer(answer: str, intent: str, query: str) -> str:
    text = clean_text(answer)

    if intent == "phone":
        phone = extract_phone(answer)
        if phone:
            if "garda" in query.lower():
                return f"The Garda Confidential Line is {phone}."
            return f"The contact number is {phone}."
        return text

    return text


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
    best_score = -1.0
    query_l = query.lower()

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

        score = cosine_similarity(query_embedding, embedding)

        content_l = content.lower()
        heading_l = section_heading.lower()
        title_l = page_title.lower()

        for word in re.findall(r"\w+", query_l):
            if len(word) > 3:
                if word in heading_l:
                    score += 0.20
                elif word in title_l:
                    score += 0.10
                elif word in content_l:
                    score += 0.05

        if intent == "phone":
            if extract_phone(content):
                score += 1.2
            if "call" in content_l or "contact" in content_l or "line" in content_l or "number" in content_l:
                score += 0.5
            if "garda" in query_l and "garda" in content_l:
                score += 1.8
            if "confidential" in query_l and "confidential" in content_l:
                score += 0.8

            # Strong country-specific preference
            if user_region == "canada":
                if region == "canada":
                    score += 2.0
                if source_site == "rcmp_ca":
                    score += 2.0
                if "canada" in title_l or "canada" in heading_l or "canada" in content_l:
                    score += 1.0

            if user_region == "ireland":
                if region == "ireland":
                    score += 2.0
                if source_site == "citizensinformation_ie":
                    score += 1.5
                if "ireland" in title_l or "ireland" in heading_l or "ireland" in content_l:
                    score += 1.0

            if user_region == "uk":
                if region == "uk":
                    score += 2.0
                if source_site in {"modernslavery_uk", "modernslaveryhelpline_org"}:
                    score += 1.5

            if user_region == "united_states":
                if region == "united_states":
                    score += 2.0
                if source_site == "humantraffickinghotline":
                    score += 1.5

        if intent == "definition":
            if "what is" in heading_l or "definition" in heading_l:
                score += 1.0
            if extract_phone(content):
                score -= 0.8

        if intent == "signs":
            if "sign" in heading_l or "indicator" in heading_l:
                score += 1.0
            if "sign" in title_l:
                score += 0.4

        if intent == "tactics":
            if "recruit" in heading_l or "tactic" in heading_l or "method" in heading_l:
                score += 1.0
            if "recruit" in content_l:
                score += 0.4

        if intent == "steps":
            if "report" in heading_l or "contact" in heading_l or "help" in heading_l:
                score += 0.8

        if user_region and region == user_region:
            score += 0.5

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
                "confidence": round(score, 3),
                "score": round(score, 3),
            }

    if not best or best_score < 0.70:
        return None

    best["answer"] = format_answer(best["answer"], intent, query)
    return best
