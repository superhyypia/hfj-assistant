import json
import os
from openai import OpenAI

from db import get_db_connection
from utils import normalize_country_key

_client = None


def get_openai_client():
    global _client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    if _client is None:
        _client = OpenAI(api_key=api_key)

    return _client


def get_ai_country_support(country_name: str, language: str = "en"):
    client = get_openai_client()
    if not client:
        return None

    country_key = normalize_country_key(country_name)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload_json
                FROM ai_country_support_cache
                WHERE country_key = %s AND language = %s
                """,
                (country_key, language),
            )
            row = cur.fetchone()

    if row:
        try:
            return json.loads(row[0])
        except Exception:
            pass

    response_language = "Spanish" if language == "es" else "English"
    title = (
        f"Contactos locales adicionales para {country_name}"
        if language == "es"
        else f"Additional local contacts for {country_name}"
    )

    response = client.responses.create(
        model="gpt-4o-mini",
        input=f"""
You are helping build a victim-support assistant.

Find official or highly credible anti-trafficking or victim-support contacts for {country_name}.

Return ONLY valid JSON in this exact schema:

{{
  "title": "{title}",
  "status": "verify",
  "contacts": [
    {{
      "organisation": "",
      "phone": "",
      "hours": "",
      "website": "",
      "email": "",
      "notes": ""
    }}
  ]
}}

Rules:
- Prefer government agencies, national helplines, or major victim-support organisations
- Do not invent contact details
- If a field is unknown, use an empty string
- Include up to 3 contacts
- No markdown
- No explanation outside JSON
- Return all labels and notes in {response_language}
"""
    )

    raw = response.output_text.strip() if response.output_text else ""
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    if not raw:
        return None

    try:
        data = json.loads(raw)
    except Exception:
        data = {
            "title": title,
            "status": "verify",
            "contacts": [],
            "raw_text": raw,
        }

    if "title" not in data:
        data["title"] = title
    if "status" not in data:
        data["status"] = "verify"
    if "contacts" not in data or not isinstance(data["contacts"], list):
        data["contacts"] = []

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_country_support_cache (country_key, country_name, language, payload_json, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (country_key)
                DO UPDATE SET
                    country_name = EXCLUDED.country_name,
                    language = EXCLUDED.language,
                    payload_json = EXCLUDED.payload_json,
                    updated_at = NOW()
                """,
                (country_key, country_name, language, json.dumps(data)),
            )
        conn.commit()

    return data


def translate_to_spanish(text: str) -> str:
    client = get_openai_client()
    if not client or not text.strip():
        return text

    response = client.responses.create(
        model="gpt-4o-mini",
        input=f"""
Translate the following support information into Spanish.
Keep it clear, calm, and structured.
Do not add extra advice.
Do not remove important details.

Text:
{text}
"""
    )

    return response.output_text.strip() if response.output_text else text


def polish_retrieved_answer(query: str, retrieved_text: str, language: str = "en") -> str:
    client = get_openai_client()
    if not client or not retrieved_text.strip():
        return retrieved_text

    response_language = "Spanish" if language == "es" else "English"

    response = client.responses.create(
        model="gpt-4o-mini",
        input=f"""
You are polishing a trusted support answer for a trafficking-awareness assistant.

Respond in {response_language}.

You must ONLY use the information provided in the retrieved text below.
Do NOT add facts, phone numbers, organisations, or advice that are not present in the retrieved text.
Do NOT mention that you are using retrieved text.

Formatting rules:
- Keep the answer concise
- Prefer short bullet points for signs, steps, or key facts
- Use plain language
- No markdown headings
- Maximum 5 bullets
- If the query asks "what is", answer in 1 short paragraph followed by bullets only if helpful
- If the query asks about signs, warning signs, or indicators, use bullets
- If the retrieved text is not sufficient, keep the answer brief and conservative

User question:
{query}

Retrieved text:
{retrieved_text}
"""
    )

    return response.output_text.strip() if response.output_text else retrieved_text
