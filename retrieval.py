from db import get_db_connection
from ai import translate_to_spanish
from utils import clean_answer_text


def score_chunk(
    query: str,
    title: str,
    heading: str | None,
    content: str,
    source_site: str,
    region: str,
    content_type: str,
    user_region: str | None,
) -> float:
    import re

    query_terms = [t for t in re.findall(r"[a-z0-9áéíóúñ]+", query.lower()) if len(t) > 2]
    if not query_terms:
        return 0.0

    title_l = (title or "").lower()
    heading_l = (heading or "").lower()
    content_l = (content or "").lower()
    query_l = query.lower()

    score = 0.0

    for term in query_terms:
        if term in title_l:
            score += 4.0
        if term in heading_l:
            score += 3.0
        if term in content_l:
            score += 1.0

    exact_phrases = [
        "human trafficking",
        "spot the signs",
        "warning signs",
        "get help",
        "forced labour",
        "forced labor",
        "sex trafficking",
        "sexual exploitation",
        "forced sexual exploitation",
        "report modern slavery",
        "trata de personas",
        "explotación sexual",
        "explotacion sexual",
        "señales de trata",
        "senales de trata",
    ]

    for phrase in exact_phrases:
        if phrase in query_l and (
            phrase in title_l or phrase in heading_l or phrase in content_l
        ):
            score += 5.0

    if user_region and region == user_region:
        score += 6.0

    if user_region == "ireland" and source_site == "hse":
        score += 4.0

    if user_region == "uk" and source_site == "modernslavery_uk":
        score += 4.0

    if "report" in query_l and content_type == "reporting":
        score += 4.0

    if "help" in query_l or "ayuda" in query_l:
        if content_type == "support":
            score += 4.0

    if (
        "sign" in query_l
        or "what is" in query_l
        or "what are the signs" in query_l
        or "sexual exploitation" in query_l
        or "señales" in query_l
        or "senales" in query_l
        or "qué es" in query_l
        or "que es" in query_l
        or "explotación" in query_l
        or "explotacion" in query_l
    ) and content_type == "education":
        score += 3.0

    return score


def find_match(query: str, user_region: str | None = None, language: str = "en"):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_url, source_site, region, content_type, page_title, section_heading, content
                FROM hfj_content_chunks
                """
            )
            rows = cur.fetchall()

    scored = []

    for row in rows:
        score = score_chunk(
            query=query,
            title=row[4],
            heading=row[5],
            content=row[6],
            source_site=row[1],
            region=row[2],
            content_type=row[3],
            user_region=user_region,
        )
        if score > 1:
            scored.append((score, row))

    scored.sort(reverse=True, key=lambda x: x[0])

    if not scored:
        return None

    best_score, best_row = scored[0]
    selected_chunks = [best_row[6]]

    for score, row in scored[1:3]:
        same_section = row[5] == best_row[5]
        close_score = score >= best_score * 0.85
        if same_section and close_score:
            selected_chunks.append(row[6])

    combined = clean_answer_text("\n\n".join(selected_chunks))
    answer = translate_to_spanish(combined) if language == "es" else combined

    return {
        "source": best_row[0],
        "source_site": best_row[1],
        "region": best_row[2],
        "content_type": best_row[3],
        "title": best_row[4],
        "section_heading": best_row[5],
        "answer": answer[:1200],
    }
