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
# Text helpers
# ---------------------------
def extract_phone_number(text: str) -> Optional[str]:
    patterns = [
        r"\b\d{3,4}\s?\d{3}\s?\d{3}\b",
        r"\b\d{3,4}\s?\d{3}\b",
        r"\b1-\d{3}-\d{3}-\d{4}\b",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            return matches[0]
    return None


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list[str]:
    text = normalize_spaces(text)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def clean_sentence(text: str, max_len: int = 260) -> str:
    text = normalize_spaces(text)
    if len(text) <= max_len:
        return text
    trimmed = text[:max_len].rsplit(" ", 1)[0].strip()
    return trimmed + "..."


def source_name(source_site: str) -> str:
    return source_site.replace("_", " ").title() if source_site else "Source"


# ---------------------------
# Intent detection
# ---------------------------
def detect_intent(query: str) -> str:
    q = query.lower().strip()

    phone_keywords = [
        "phone number",
        "number",
        "hotline",
        "helpline",
        "line",
        "call",
        "contact number",
    ]
    if any(term in q for term in phone_keywords):
        return "phone"

    if any(term in q for term in ["recruit", "recruiting", "recruitment", "tactic", "tactics", "method", "methods"]):
        return "tactics"

    if any(term in q for term in ["sign", "signs", "indicator", "indicators", "spot the signs"]):
        return "signs"

    if q.startswith("what is ") or q.startswith("what are ") or q.startswith("who is "):
        return "definition"

    how_prefixes = [
        "how do ",
        "how can ",
        "how should ",
        "what should i do",
        "what do i do",
        "how to ",
    ]
    if any(q.startswith(prefix) for prefix in how_prefixes):
        return "steps"

    return "summary"


# ---------------------------
# Formatting
# ---------------------------
def format_phone_answer(answer: str, source_site: str, query: str) -> str:
    phone = extract_phone_number(answer)
    src = source_name(source_site)

    if "garda" in query.lower() and phone:
        return (
            f"The Garda Confidential Line is {phone}.\n\n"
            f"You can use this number to report concerns confidentially."
        )

    if phone:
        return f"The contact number is {phone}."

    return clean_sentence(answer)


def format_definition_answer(answer: str, source_site: str) -> str:
    sentences = split_sentences(answer)
    summary = " ".join(sentences[:2]) if sentences else answer
    return clean_sentence(summary, max_len=260)


def lines_from_text(answer: str, max_items: int = 4) -> list[str]:
    text = normalize_spaces(answer)

    split_candidates = re.split(r"(?:•|-|\*|\d+\.)\s+", text)
    cleaned = [item.strip(" .;:") for item in split_candidates if len(item.strip()) > 18]

    if len(cleaned) >= 2:
        deduped = []
        for item in cleaned:
            if item not in deduped:
                deduped.append(item)
            if len(deduped) >= max_items:
                break
        return deduped

    sentences = split_sentences(answer)
    deduped = []
    for sentence in sentences:
        if len(sentence) < 20:
            continue
        if sentence not in deduped:
            deduped.append(sentence)
        if len(deduped) >= max_items:
            break
    return deduped


def format_steps_answer(answer: str, source_site: str) -> str:
    lines = lines_from_text(answer, max_items=3)

    if not lines:
        return clean_sentence(answer)

    bullets = "\n".join(f"• {line}" for line in lines)
    return f"Here are the key steps:\n{bullets}"


def format_tactics_answer(answer: str, source_site: str) -> str:
    lines = lines_from_text(answer, max_items=5)

    if not lines:
        return clean_sentence(answer)

    bullets = "\n".join(f"• {line}" for line in lines)
    return f"Common recruiting tactics include:\n{bullets}"


def format_signs_answer(answer: str, source_site: str) -> str:
    lines = lines_from_text(answer, max_items=5)

    if not lines:
        return clean_sentence(answer)

    bullets = "\n".join(f"• {line}" for line in lines)
    return f"Common signs can include:\n{bullets}"


def format_summary_answer(answer: str, source_site: str) -> str:
    return clean_sentence(answer, max_len=240)


def format_answer(answer: str, source_site: str, query: str) -> str:
    intent = detect_intent(query)

    if intent == "phone":
        return format_phone_answer(answer, source_site, query)
    if intent == "definition":
        return format_definition_answer(answer, source_site)
    if intent == "steps":
        return format_steps_answer(answer, source_site)
    if intent == "tactics":
        return format_tactics_answer(answer, source_site)
    if intent == "signs":
        return format_signs_answer(answer, source_site)

    return format_summary_answer(answer, source_site)


# ---------------------------
# Keyword fallback
# ---------------------------
def keyword_search(query: str, limit: int = 8) -> Optional[dict]:
    terms = [t.strip().lower() for t in re.findall(r"[a-zA-Z']+", query) if len(t) > 3]

    if not terms:
        return None

    like_clauses = " OR ".join(
        ["content ILIKE %s OR COALESCE(section_heading,'') ILIKE %s" for _ in terms]
    )
    values = []
    for term in terms:
        values.extend([f"%{term}%", f"%{term}%"])

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    content,
                    source_url,
                    page_title,
                    section_heading,
                    source_site,
                    region,
                    source_name,
                    source_domain
                FROM hfj_content_chunks
                WHERE {like_clauses}
                LIMIT {limit}
                """,
                values,
            )
            rows = cur.fetchall()

    if not rows:
        return None

    query_l = query.lower()
    best_row = None
    best_score = -1.0

    for row in rows:
        content = row[0] or ""
        heading = row[3] or ""
        page_title = row[2] or ""
        source_site = row[4] or ""
        content_l = content.lower()
        heading_l = heading.lower()
        title_l = page_title.lower()

        score = 0.0

        for term in terms:
            if term in heading_l:
                score += 2.5
            if term in title_l:
                score += 1.0
            if term in content_l:
                score += 1.2

        intent = detect_intent(query)

        if intent == "tactics":
            for term in ["recruit", "recruiting", "recruitment", "tactic", "tactics", "method", "methods", "lure", "groom"]:
                if term in heading_l:
                    score += 3.0
                if term in content_l:
                    score += 1.2

        if intent == "signs":
            for term in ["sign", "signs", "indicator", "indicators", "warning"]:
                if term in heading_l:
                    score += 3.0
                if term in content_l:
                    score += 1.2

        if intent in {"tactics", "signs", "steps"}:
            if "what is human trafficking" in heading_l or "human trafficking is" in content_l[:120]:
                score -= 2.5

        if source_site in {"rcmp_ca", "citizensinformation_ie", "hopeforjustice", "hse", "modernslavery_uk"}:
            score += 0.4

        if score > best_score:
            best_score = score
            best_row = row

    if not best_row:
        return None

    return {
        "answer": format_answer(best_row[0], best_row[4], query),
        "source": best_row[1],
        "title": best_row[2],
        "section_heading": best_row[3],
        "source_site": best_row[4],
        "source_name": best_row[6],
        "source_domain": best_row[7],
        "confidence": 0.65,
        "score": round(best_score, 3),
    }


# ---------------------------
# Main retrieval
# ---------------------------
def find_match(query: str, user_region: str | None = None, language: str = "en"):
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
    second_best_score = -1.0
    query_l = query.lower()
    intent = detect_intent(query)

    intent_terms = {
        "tactics": ["recruit", "recruiting", "recruitment", "tactic", "tactics", "method", "methods", "lure", "groom"],
        "signs": ["sign", "signs", "indicator", "indicators", "warning"],
        "steps": ["report", "help", "support", "call", "contact", "tell", "speak"],
        "phone": ["line", "number", "phone", "contact", "hotline", "helpline", "call"],
        "definition": ["what is", "what are", "meaning", "defined"],
    }

    for row in rows:
        content = row[0] or ""
        embedding_json = row[1]
        source_url = row[2]
        page_title = row[3] or ""
        section_heading = row[4] or ""
        source_site = row[5] or ""
        region = row[6]
        chunk_source_name = row[7] or ""
        chunk_source_domain = row[8] or ""

        if not embedding_json:
            continue

        try:
            embedding = json.loads(embedding_json)
        except Exception:
            continue

        similarity = cosine_similarity(query_embedding, embedding)
        score = similarity

        content_l = content.lower()
        heading_l = section_heading.lower()
        title_l = page_title.lower()

        for word in re.findall(r"[a-zA-Z']+", query_l):
            if len(word) <= 3:
                continue
            if word in heading_l:
                score += 0.18
            elif word in title_l:
                score += 0.06
            elif word in content_l:
                score += 0.03

        for term in intent_terms.get(intent, []):
            if term in heading_l:
                score += 0.9
            if term in content_l:
                score += 0.18

        if "garda" in query_l and "garda" in content_l:
            score += 0.8
        if "confidential" in query_l and "confidential" in content_l:
            score += 0.4
        if "line" in query_l and "call" in content_l:
            score += 0.25

        if user_region and region == user_region:
            score += 0.18

        if source_site in {"rcmp_ca", "citizensinformation_ie", "hopeforjustice", "hse", "modernslavery_uk"}:
            score += 0.08

        if intent in {"tactics", "signs", "steps"}:
            if "what is human trafficking" in heading_l:
                score -= 0.8
            if heading_l in {"human trafficking", "what is trafficking?", "what is human trafficking?"}:
                score -= 0.8
            if content_l.startswith("human trafficking is"):
                score -= 0.6

        candidate = {
            "answer": content,
            "source": source_url,
            "title": page_title,
            "section_heading": section_heading,
            "source_site": source_site,
            "source_name": chunk_source_name,
            "source_domain": chunk_source_domain,
            "confidence": round(score, 3),
            "score": round(score, 3),
        }

        if score > best_score:
            second_best_score = best_score
            best_score = score
            best = candidate
        elif score > second_best_score:
            second_best_score = score

    if not best or best_score < 0.72:
        keyword_result = keyword_search(query)
        if keyword_result:
            return keyword_result

    if best:
        best["answer"] = format_answer(
            best["answer"],
            best.get("source_site", "source"),
            query,
        )
        best["second_score"] = round(second_best_score, 3) if second_best_score > -1 else None

    return best
