from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

from db import init_db
from ingest import ingest_all_sources
from retrieval import find_match
from agent import decide_next_step

from support import (
    build_country_response,
    build_help_prompt,
    build_unknown_location_response,
    build_us_state_response,
)

from utils import (
    SESSION_STATE,
    add_safety_footer,
    detect_language,
    detect_location,
    infer_user_region,
    is_help_trigger,
    is_unknown_location_reply,
    looks_like_general_question,
    normalize,
)
from ai import get_openai_client

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    language: str | None = None


@app.on_event("startup")
def startup_event():
    init_db()
    ingest_all_sources()


@app.get("/")
def root():
    return {"message": "HFJ Assistant is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db-check")
def db_check():
    from support import get_support_route

    try:
        return {
            "status": "ok",
            "database_connected": True,
            "sample_routes": {
                "ireland": get_support_route("ireland"),
                "uk": get_support_route("uk"),
                "united_states": get_support_route("united_states"),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/routes")
def routes():
    from db import get_db_connection

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT region_key, display_name, emergency_text, phone, website
                    FROM hfj_support_routes
                    ORDER BY display_name
                    """
                )
                rows = cur.fetchall()

        return {
            "routes": [
                {
                    "region_key": row[0],
                    "display_name": row[1],
                    "emergency_text": row[2],
                    "phone": row[3],
                    "website": row[4],
                }
                for row in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/content-check")
def content_check():
    from db import get_db_connection

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source_site, region, content_type, page_title, COUNT(*)
                    FROM hfj_content_chunks
                    GROUP BY source_site, region, content_type, page_title
                    ORDER BY source_site, page_title
                    """
                )
                rows = cur.fetchall()

        return {
            "pages": [
                {
                    "source_site": row[0],
                    "region": row[1],
                    "content_type": row[2],
                    "page_title": row[3],
                    "chunk_count": row[4],
                }
                for row in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/reingest-all")
def reingest_all():
    try:
        return {"status": "ok", "results": ingest_all_sources()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest error: {str(e)}")


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        user_input = req.message.strip()
        text = normalize(user_input)

        if not user_input:
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        language = req.language if req.language in {"en", "es"} else detect_language(user_input)

        session_id = req.session_id or str(uuid.uuid4())
        session = SESSION_STATE.setdefault(
            session_id,
            {
                "stage": None,
                "saved_location": None,
                "language": language,
            },
        )
        session["language"] = language

        # Break out of pending location flow if user switches to a general question.
        if session["stage"] == "awaiting_location" and looks_like_general_question(text):
            session["stage"] = None
            session["saved_location"] = None

        # If we are waiting for a location, prioritize that flow.
        if session["stage"] == "awaiting_location":
            if is_unknown_location_reply(user_input):
                session["stage"] = None
                session["saved_location"] = None
                result = build_unknown_location_response(session_id, language=language)
                result["language"] = language
                return result

            location = detect_location(user_input, text)

            if location:
                session["stage"] = None
                session["saved_location"] = None

                if location["kind"] == "state":
                    result = build_us_state_response(location["value"], language=language)
                else:
                    result = build_country_response(location["value"], language=language)

                result["session_id"] = session_id
                result["language"] = language
                return result

            result = {
                "reply": (
                    "Please tell me your country or state so I can give you the right support options."
                    if language == "en"
                    else "Por favor, dime tu país o estado para poder darte las opciones de apoyo adecuadas."
                ),
                "source": "https://hopeforjustice.org/get-help/",
                "type": "hfj",
                "title": "Location needed" if language == "en" else "Ubicación necesaria",
                "session_id": session_id,
                "language": language,
            }
            return result

        # Direct location-only queries.
        location = detect_location(user_input, text)
        if location:
            if location["kind"] == "state":
                result = build_us_state_response(location["value"], language=language)
                result["session_id"] = session_id
                result["language"] = language
                return result

            if location["kind"] == "country":
                result = build_country_response(location["value"], language=language)
                result["session_id"] = session_id
                result["language"] = language
                return result

        # Educational questions should try retrieval first.
        if looks_like_general_question(text):
            user_region = infer_user_region(location)
            match = find_match(text, user_region=user_region, language=language)

            if match and match["confidence"] in {"high", "medium"}:
                return {
                    "reply": add_safety_footer(match["answer"], language),
                    "source": match["source"],
                    "type": "hfj",
                    "title": match["title"],
                    "section_heading": match["section_heading"],
                    "source_site": match["source_site"],
                    "confidence": match["confidence"],
                    "score": match["score"],
                    "second_score": match.get("second_score"),
                    "session_id": session_id,
                    "language": language,
                }

        # Help / distress flow.
        if is_help_trigger(text):
            detected_location = detect_location(user_input, text)

            if detected_location and detected_location["confidence"] == "high":
                if detected_location["kind"] == "state":
                    result = build_us_state_response(detected_location["value"], language=language)
                else:
                    result = build_country_response(detected_location["value"], language=language)

                prefix = (
                    "I’m really sorry this may be happening.\n\n"
                    "If there is immediate danger, contact emergency services now.\n\n"
                    if language == "en"
                    else "Siento mucho que esto pueda estar ocurriendo.\n\n"
                    "Si hay peligro inmediato, contacta ahora con los servicios de emergencia.\n\n"
                )
                result["reply"] = prefix + result["reply"]
                result["session_id"] = session_id
                result["language"] = language
                return result

            session["stage"] = "awaiting_location"
            result = build_help_prompt(detected_location, session_id, language=language)
            result["language"] = language
            return result

        # General retrieval pass for non-help, non-location questions.
        user_region = infer_user_region(location)
        match = find_match(text, user_region=user_region, language=language)

        if match and match["confidence"] in {"high", "medium"}:
            return {
                "reply": add_safety_footer(match["answer"], language),
                "source": match["source"],
                "type": "hfj",
                "title": match["title"],
                "section_heading": match["section_heading"],
                "source_site": match["source_site"],
                "confidence": match["confidence"],
                "score": match["score"],
                "second_score": match.get("second_score"),
                "session_id": session_id,
                "language": language,
            }

        # Low-confidence or no retrieval match falls back to OpenAI.
        client = get_openai_client()
        if not client:
            raise HTTPException(status_code=500, detail="Missing API key")

        response = client.responses.create(
            model="gpt-4o",
            input=f"""
You are the Hope for Justice assistant.

Respond in {"Spanish" if language == "es" else "English"}.

Provide clear, structured, calm, supportive answers about trafficking-related topics.
Do not provide investigative or vigilante advice.
If someone may need help, encourage official support routes.

Question: {user_input}
"""
        )

        return {
            "reply": response.output_text,
            "source": "AI-generated general guidance",
            "type": "ai",
            "title": "General guidance" if language == "en" else "Orientación general",
            "session_id": session_id,
            "language": language,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {type(e).__name__}: {str(e)}")
