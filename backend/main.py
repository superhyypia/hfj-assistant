from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

from agent import is_low_visibility_signal, plan_next_actions
from ai import get_openai_client
from db import init_db, check_db_health, get_sources, get_db_connection
from ingest import ingest_all_sources
from retrieval import find_match
from support import (
    build_country_response,
    build_help_prompt,
    build_low_visibility_response,
    build_unknown_location_response,
    build_us_state_response,
    get_support_route,
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

class SourceCreate(BaseModel):
    name: str
    domain: str
    base_url: str | None = None
    region: str = "global"
    source_type: str = "official"
    priority: int = 100
    status: str = "active"


@app.on_event("startup")
def startup_event():
    init_db()


@app.get("/")
def root():
    return {"message": "HFJ Assistant is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/admin/health")
def admin_health():
    try:
        db_ok = check_db_health()
        return {
            "status": "ok" if db_ok else "error",
            "database": "connected" if db_ok else "not connected",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@app.get("/admin/sources")
def get_admin_sources():
    try:
        return {"sources": get_sources()}
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }

from pydantic import BaseModel

class SourceUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    base_url: str | None = None
    region: str | None = None
    source_type: str | None = None
    priority: int | None = None
    status: str | None = None


@app.patch("/admin/sources/{source_id}")
def update_source(source_id: int, update: SourceUpdate):
    from db import get_db_connection

    fields = []
    values = []

    for field, value in update.dict(exclude_none=True).items():
        fields.append(f"{field} = %s")
        values.append(value)

    if not fields:
        return {"status": "no changes"}

    values.append(source_id)

    query = f"""
        UPDATE hfj_sources
        SET {', '.join(fields)}
        WHERE id = %s
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, values)
            conn.commit()

        return {"status": "ok"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/admin/sources")
def create_source(source: SourceCreate):
    try:
        from db import get_db_connection

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO hfj_sources
                    (name, domain, base_url, region, source_type, priority, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        source.name,
                        source.domain,
                        source.base_url,
                        source.region,
                        source.source_type,
                        source.priority,
                        source.status,
                    ),
                )
                new_id = cur.fetchone()[0]

            conn.commit()

        return {"status": "ok", "id": new_id}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/db-check")
def db_check():
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

        if session["stage"] == "awaiting_location" and looks_like_general_question(text):
            session["stage"] = None
            session["saved_location"] = None

        location = detect_location(user_input, text)
        is_help = is_help_trigger(text)
        is_unknown_location = is_unknown_location_reply(user_input)
        is_low_visibility = is_low_visibility_signal(user_input)
        user_region = infer_user_region(location or session.get("saved_location"))

        retrieval_match = None
        if looks_like_general_question(text) or not is_help:
            retrieval_match = find_match(text, user_region=user_region, language=language)

        plan = plan_next_actions(
            text=text,
            session=session,
            has_location=bool(location),
            is_help=is_help,
            is_unknown_location=is_unknown_location,
            is_low_visibility=is_low_visibility,
            retrieval_match=retrieval_match,
        )

        if plan["actions"] == ["unknown_location_support"]:
            session["stage"] = None
            session["saved_location"] = None
            result = build_unknown_location_response(session_id, language=language)
            result["language"] = language
            result["agent_plan"] = plan
            return result

        if plan["actions"] == ["low_visibility_support"]:
            session["stage"] = "awaiting_location"
            result = build_low_visibility_response(session_id, language=language)
            result["language"] = language
            result["agent_plan"] = plan
            return result

        if plan["actions"] == ["route_support"]:
            session["stage"] = None

            if location:
                session["saved_location"] = location

            chosen_location = location or session.get("saved_location")
            if not chosen_location:
                session["stage"] = "awaiting_location"
                result = build_help_prompt(None, session_id, language=language)
                result["language"] = language
                result["agent_plan"] = plan
                return result

            if chosen_location["kind"] == "state":
                result = build_us_state_response(chosen_location["value"], language=language)
            else:
                result = build_country_response(chosen_location["value"], language=language)

            result["session_id"] = session_id
            result["language"] = language
            result["agent_plan"] = plan
            return result

        if plan["actions"] == ["ask_location"]:
            session["stage"] = "awaiting_location"
            result = build_help_prompt(location, session_id, language=language)
            result["language"] = language
            result["agent_plan"] = plan
            return result

        if plan["actions"] == ["ask_location_again"]:
            return {
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
                "agent_plan": plan,
            }

        if plan["actions"] in (["answer_from_retrieval"], ["answer_with_polish"]) and retrieval_match:
            return {
                "reply": add_safety_footer(retrieval_match["answer"], language),
                "source": retrieval_match["source"],
                "type": "hfj",
                "title": retrieval_match["title"],
                "section_heading": retrieval_match["section_heading"],
                "source_site": retrieval_match["source_site"],
                "confidence": retrieval_match["confidence"],
                "score": retrieval_match["score"],
                "second_score": retrieval_match.get("second_score"),
                "session_id": session_id,
                "language": language,
                "agent_plan": plan,
            }

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

Formatting rules:
- Keep answers concise
- Use short bullet points when giving advice or steps
- Avoid long paragraphs
- Do not use markdown headings

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
            "agent_plan": plan,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {type(e).__name__}: {str(e)}")
