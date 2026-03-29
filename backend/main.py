from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

from agent import is_low_visibility_signal, plan_next_actions
from ai import get_openai_client
from db import (
    init_db,
    check_db_health,
    get_sources,
    log_conversation_turn,
    get_conversations,
    get_conversation_by_id,
)
from ingest import ingest_all_sources, ingest_source_by_id
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
    clean_answer_text,
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

init_db()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    language: str | None = None


class SourceUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    base_url: str | None = None
    region: str | None = None
    source_type: str | None = None
    priority: int | None = None
    status: str | None = None


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
    return {"sources": get_sources()}


@app.get("/admin/conversations")
def admin_conversations(limit: int = 100):
    return {"conversations": get_conversations(limit=limit)}


@app.get("/admin/conversations/{conversation_id}")
def admin_conversation_detail(conversation_id: int):
    conversation = get_conversation_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/admin/sources")
def create_source(source: SourceCreate):
    from db import get_db_connection

    try:
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
                        source.name.strip(),
                        source.domain.strip(),
                        source.base_url.strip() if source.base_url else None,
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


@app.patch("/admin/sources/{source_id}")
def update_source(source_id: int, update: SourceUpdate):
    from db import get_db_connection

    fields = []
    values = []

    update_data = update.dict(exclude_none=True)

    for field, value in update_data.items():
        fields.append(f"{field} = %s")
        values.append(value)

    if not fields:
        return {"status": "no changes"}

    values.append(source_id)

    query = f"""
        UPDATE hfj_sources
        SET {", ".join(fields)}
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


@app.post("/admin/sources/{source_id}/ingest")
def ingest_single_source(source_id: int):
    try:
        result = ingest_source_by_id(source_id)
        return {"status": "ok", "result": result}
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

        if session["stage"] == "awaiting_location" and looks_like_general_question(text):
            session["stage"] = None
            session["saved_location"] = None

        location = detect_location(user_input, text)
        is_help = is_help_trigger(text)
        is_unknown_location = is_unknown_location_reply(user_input)
        is_low_visibility = is_low_visibility_signal(user_input)
        user_region = infer_user_region(location or session.get("saved_location"))

        retrieval_match = None
        
        informational_query = (
            looks_like_general_question(text)
            or any(word in text for word in ["signs", "recruit", "define", "what is", "what are"])
        )

        if informational_query:
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

            log_conversation_turn(
                session_id=session_id,
                user_message=user_input,
                assistant_reply=result["reply"],
                response_type=result.get("type"),
                title=result.get("title"),
                source=result.get("source"),
                source_site=result.get("source_site"),
                source_name=result.get("source_name"),
                source_domain=result.get("source_domain"),
                agent_action=(plan.get("actions") or [None])[0],
                agent_reason=plan.get("reason"),
                score=None,
                region_detected=user_region,
                language=language,
                is_fallback=False,
            )
            return result

        if plan["actions"] == ["low_visibility_support"]:
            session["stage"] = "awaiting_location"
            result = build_low_visibility_response(session_id, language=language)
            result["language"] = language
            result["agent_plan"] = plan

            log_conversation_turn(
                session_id=session_id,
                user_message=user_input,
                assistant_reply=result["reply"],
                response_type=result.get("type"),
                title=result.get("title"),
                source=result.get("source"),
                source_site=result.get("source_site"),
                source_name=result.get("source_name"),
                source_domain=result.get("source_domain"),
                agent_action=(plan.get("actions") or [None])[0],
                agent_reason=plan.get("reason"),
                score=None,
                region_detected=user_region,
                language=language,
                is_fallback=False,
            )
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

                log_conversation_turn(
                    session_id=session_id,
                    user_message=user_input,
                    assistant_reply=result["reply"],
                    response_type=result.get("type"),
                    title=result.get("title"),
                    source=result.get("source"),
                    source_site=result.get("source_site"),
                    source_name=result.get("source_name"),
                    source_domain=result.get("source_domain"),
                    agent_action=(plan.get("actions") or [None])[0],
                    agent_reason=plan.get("reason"),
                    score=None,
                    region_detected=user_region,
                    language=language,
                    is_fallback=False,
                )
                return result

            if chosen_location["kind"] == "state":
                result = build_us_state_response(chosen_location["value"], language=language)
            else:
                result = build_country_response(chosen_location["value"], language=language)

            result["session_id"] = session_id
            result["language"] = language
            result["agent_plan"] = plan

            log_conversation_turn(
                session_id=session_id,
                user_message=user_input,
                assistant_reply=result["reply"],
                response_type=result.get("type"),
                title=result.get("title"),
                source=result.get("source"),
                source_site=result.get("source_site"),
                source_name=result.get("source_name"),
                source_domain=result.get("source_domain"),
                agent_action=(plan.get("actions") or [None])[0],
                agent_reason=plan.get("reason"),
                score=None,
                region_detected=user_region,
                language=language,
                is_fallback=False,
            )
            return result

        if plan["actions"] == ["ask_location"]:
            session["stage"] = "awaiting_location"
            result = build_help_prompt(location, session_id, language=language)
            result["language"] = language
            result["agent_plan"] = plan

            log_conversation_turn(
                session_id=session_id,
                user_message=user_input,
                assistant_reply=result["reply"],
                response_type=result.get("type"),
                title=result.get("title"),
                source=result.get("source"),
                source_site=result.get("source_site"),
                source_name=result.get("source_name"),
                source_domain=result.get("source_domain"),
                agent_action=(plan.get("actions") or [None])[0],
                agent_reason=plan.get("reason"),
                score=None,
                region_detected=user_region,
                language=language,
                is_fallback=False,
            )
            return result

        if plan["actions"] == ["ask_location_again"]:
            result = {
                "reply": (
                    "Please tell me your country or state so I can give you the right support options."
                    if language == "en"
                    else "Por favor, dime tu país o estado para poder darte las opciones de apoyo adecuadas."
                ),
                "source": "https://hopeforjustice.org/get-help/",
                "type": "hfj",
                "title": "Location needed" if language == "en" else "Ubicación necesaria",
                "source_site": "hopeforjustice",
                "source_name": "Hope for Justice",
                "source_domain": "hopeforjustice.org",
                "session_id": session_id,
                "language": language,
                "agent_plan": plan,
            }

            log_conversation_turn(
                session_id=session_id,
                user_message=user_input,
                assistant_reply=result["reply"],
                response_type=result.get("type"),
                title=result.get("title"),
                source=result.get("source"),
                source_site=result.get("source_site"),
                source_name=result.get("source_name"),
                source_domain=result.get("source_domain"),
                agent_action=(plan.get("actions") or [None])[0],
                agent_reason=plan.get("reason"),
                score=None,
                region_detected=user_region,
                language=language,
                is_fallback=False,
            )
            return result

        if plan["actions"] in (["answer_from_retrieval"], ["answer_with_polish"]) and retrieval_match:
            result = {
                "reply": add_safety_footer(
                    clean_answer_text(retrieval_match["answer"]),
                    language
                ),
                "source": retrieval_match.get("source"),
                "type": "hfj",
                "title": retrieval_match.get("title"),
                "section_heading": retrieval_match.get("section_heading"),
                "source_site": retrieval_match.get("source_site") or "unknown",
                "source_name": retrieval_match.get("source_name"),
                "source_domain": retrieval_match.get("source_domain"),
                "confidence": retrieval_match.get("confidence"),
                "score": retrieval_match.get("score"),
                "second_score": retrieval_match.get("second_score"),
                "session_id": session_id,
                "language": language,
                "agent_plan": plan,
            }

            log_conversation_turn(
                session_id=session_id,
                user_message=user_input,
                assistant_reply=result["reply"],
                response_type=result.get("type"),
                title=result.get("title"),
                source=result.get("source"),
                source_site=result.get("source_site"),
                source_name=result.get("source_name"),
                source_domain=result.get("source_domain"),
                agent_action=(plan.get("actions") or [None])[0],
                agent_reason=plan.get("reason"),
                score=result.get("score"),
                region_detected=user_region,
                language=language,
                is_fallback=False,
            )
            return result

        # 🚨 SAFETY: block AI from generating phone numbers
        contact_keywords = ["call", "contact", "number", "hotline", "helpline"]
        countries = ["ireland", "uk", "canada", "denmark", "mexico", "usa", "united states"]

        if any(k in text for k in contact_keywords) and any(c in text for c in countries):
            result = {
                "reply": (
                    "I couldn’t verify a country-specific trafficking contact number from trusted sources.\n\n"
                    "If there is immediate danger, call local emergency services.\n"
                    "If you want, I can help identify official organisations for that country."
                ),
                "source": "Trusted sources check",
                "type": "hfj",
                "title": "Verified sources not available",
                "source_site": "system",
                "source_name": "Trusted Sources Check",
                "source_domain": None,
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

        result = {
            "reply": response.output_text,
            "source": "AI-generated general guidance",
            "type": "ai",
            "title": "General guidance" if language == "en" else "Orientación general",
            "session_id": session_id,
            "language": language,
            "agent_plan": plan,
        }

        log_conversation_turn(
            session_id=session_id,
            user_message=user_input,
            assistant_reply=result["reply"],
            response_type=result.get("type"),
            title=result.get("title"),
            source=result.get("source"),
            source_site=None,
            source_name=None,
            source_domain=None,
            agent_action=(plan.get("actions") or [None])[0],
            agent_reason=plan.get("reason"),
            score=None,
            region_detected=user_region,
            language=language,
            is_fallback=True,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {type(e).__name__}: {str(e)}")
