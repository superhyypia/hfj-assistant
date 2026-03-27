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

    query_l = query.lower()
    title_l = (title or "").lower()
    heading_l = (heading or "").lower()
    content_l = (content or "").lower()

    query_terms = [t for t in re.findall(r"[a-z0-9áéíóúñ]+", query_l) if len(t) > 2]
    if not query_terms:
        return 0.0

    score = 0.0

    # Basic term scoring
    for term in query_terms:
        if term in title_l:
            score += 5.0
        if term in heading_l:
            score += 7.0
        if term in content_l:
            score += 1.5

    # Strong phrase scoring
    exact_phrases = [
        "human trafficking",
        "spot the signs",
        "warning signs",
        "signs of trafficking",
        "forced labour",
        "forced labor",
        "sex trafficking",
        "sexual exploitation",
        "forced sexual exploitation",
        "domestic servitude",
        "modern slavery",
        "trata de personas",
        "explotación sexual",
        "explotacion sexual",
        "señales de trata",
        "senales de trata",
        "signos de explotación",
        "signos de explotacion",
    ]

    for phrase in exact_phrases:
        if phrase in query_l:
            if phrase in title_l:
                score += 12.0
            if phrase in heading_l:
                score += 14.0
            if phrase in content_l:
                score += 5.0

    # Question intent bonuses
    if any(x in query_l for x in ["what is", "qué es", "que es"]):
        if content_type == "education":
            score += 4.0

    if any(x in query_l for x in ["sign", "señales", "senales", "warning", "indicator", "indicators", "signos"]):
        if content_type == "education":
            score += 6.0

    if any(x in query_l for x in ["help", "support", "ayuda", "apoyo"]):
        if content_type == "support":
            score += 6.0

    if "report" in query_l:
        if content_type == "reporting":
            score += 6.0

    # Region/source bonuses
    if user_region and region == user_region:
        score += 8.0

    if user_region == "ireland" and source_site == "hse":
        score += 5.0

    if user_region == "uk" and source_site == "modernslavery_uk":
        score += 5.0

    if user_region == "united_states" and source_site == "humantraffickinghotline":
        score += 6.0

    # Penalize vague content if no strong heading match
    if heading_l and not any(term in heading_l for term in query_terms):
        score -= 1.5

    # Penalize support pages for educational queries
    if content_type == "support" and any(x in query_l for x in ["what is", "qué es", "que es", "sign", "señales", "senales"]):
        score -= 2.0

    return max(score, 0.0)


def select_best_chunks(scored_rows: list[tuple[float, tuple]]) -> tuple[float, tuple, list[str]]:
    best_score, best_row = scored_rows[0]
    selected_chunks = [best_row[6]]

    for score, row in scored_rows[1:5]:
        same_section = row[5] == best_row[5]
        same_page = row[4] == best_row[4]
        close_score = score >= best_score * 0.88

        if same_section and same_page and close_score:
            if row[6] not in selected_chunks:
                selected_chunks.append(row[6])

    return best_score, best_row, selected_chunks


def retrieval_confidence(best_score: float, second_score: float | None = None) -> str:
    if best_score >= 28:
        return "high"
    if best_score >= 16:
        if second_score is None or best_score >= second_score * 1.25:
            return "medium"
    return "low"


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
        if score > 2:
            scored.append((score, row))

    scored.sort(reverse=True, key=lambda x: x[0])

    if not scored:
        return None

    second_score = scored[1][0] if len(scored) > 1 else None
    best_score, best_row, selected_chunks = select_best_chunks(scored)
    confidence = retrieval_confidence(best_score, second_score)

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
        "score": round(best_score, 2),
        "second_score": round(second_score, 2) if second_score is not None else None,
        "confidence": confidence,
    }
