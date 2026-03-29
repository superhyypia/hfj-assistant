import json
import re
from typing import Optional

from db import get_db_connection
from ai import embed_texts


def cosine_similarity(a, b):
    if not a or not b or len(a) != len(b):
        return -1.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return -1.0

    return dot / (norm_a * norm_b)


def extract_phone_number(text: str) -> Optional[str]:
    matches = re.findall(r"\b\d{3,4}\s?\d{3}\s?\d{3}\b", text)
    return matches[0] if matches else None


def clean_sentence(text: str, max_len: int = 220) -> str:
    text = text.strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    trimmed = text[:max_len].rsplit(" ", 1)[0].strip()
    return trimmed + "..."


def format_answer(answer: str, source_site: str, query: str) -> str:
    phone = extract_phone_number(answer)

    if "garda" in query.lower() and phone:
        return (
            f"The Garda Confidential Line is {phone}.\n\n"
            f"You can use this number to report concerns confidentially."
        )

    if phone:
        return f"The contact number is {phone}."

    return clean_sentence(answer)


def keyword_search(query: str, limit: int = 5) -> Optional[dict]:
    terms = [t.strip().lower() for t in query.split() if len(t) > 3]

    if not terms:
        return None

    like_clauses = " OR ".join(["content ILIKE %s" for _ in terms])
    values = [f"%{t}%" for t in terms]

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

    row = rows[0]

    return {
        "answer": format_answer(row[0], row[4], query),
        "source": row[1],
        "title": row[2],
        "section_heading": row[3],
        "source_site": row[4],
        "source_name": row[5],
        "source_domain": row[6],
        "confidence": 0.6,
        "score": 0.6,
    }


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
    query_l = query.lower()

    for row in rows:
        content = row[0] or ""
        embedding_json = row[1]

        if not embedding_json:
            continue

        try:
            embedding = json.loads(embedding_json)
        except Exception:
            continue

        similarity = cosine_similarity(query_embedding, embedding)
        score = similarity
        content_l = content.lower()

        if "garda" in query_l and "garda" in content_l:
            score += 0.25

        if "confidential" in query_l and "confidential" in content_l:
            score += 0.15

        if "line" in query_l and "call" in content_l:
            score += 0.1

        for word in query_l.split():
            if len(word) > 4 and word in content_l:
                score += 0.02

        region = row[6]
        if user_region and region == user_region:
            score += 0.1

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

    if not best or best_score < 0.75:
        keyword_result = keyword_search(query)
        if keyword_result:
            return keyword_result

    if best:
        best["answer"] = format_answer(
            best["answer"],
            best.get("source_site", "source"),
            query,
        )

    return best
