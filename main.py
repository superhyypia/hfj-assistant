from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import uuid
from openai import OpenAI

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

# Simple in-memory session state for MVP
SESSION_STATE = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


HFJ_KNOWLEDGE = [
    {
        "title": "What is human trafficking?",
        "source": "https://hopeforjustice.org/human-trafficking/",
        "keywords": ["what is human trafficking", "define trafficking", "what is trafficking"],
        "answer": (
            "Human trafficking is the exploitation of another person for labour, "
            "services, or commercial sex through force, fraud, or coercion.\n\n"
            "It is not just about movement — the key issue is exploitation."
        ),
    },
    {
        "title": "Spot the signs",
        "source": "https://hopeforjustice.org/spot-the-signs/",
        "keywords": ["spot the signs", "warning signs", "how do i spot", "signs of trafficking"],
        "answer": (
            "Common warning signs include:\n\n"
            "• Fear, anxiety, or inability to speak freely\n"
            "• Someone else controlling documents or movement\n"
            "• Poor living conditions or lack of pay\n"
            "• Dependency on another person\n\n"
            "Signs vary depending on the type of exploitation."
        ),
    },
    {
        "title": "Labour trafficking",
        "source": "https://hopeforjustice.org/human-trafficking/",
        "keywords": ["labour trafficking", "forced labour", "labor trafficking"],
        "answer": (
            "Labour trafficking involves exploitation through work.\n\n"
            "It may include low pay, threats, long hours, poor conditions, and restricted movement."
        ),
    },
    {
        "title": "Sex trafficking",
        "source": "https://hopeforjustice.org/human-trafficking/",
        "keywords": ["sex trafficking", "sexual exploitation"],
        "answer": (
            "Sex trafficking involves exploitation for commercial sex through "
            "force, fraud, or coercion.\n\n"
            "It may involve control, threats, or manipulation."
        ),
    },
]


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def find_match(text: str):
    best = None
    best_score = 0

    for item in HFJ_KNOWLEDGE:
        score = sum(1 for kw in item["keywords"] if kw in text)
        if score > best_score:
            best_score = score
            best = item

    return best if best_score > 0 else None


def is_help_trigger(text: str) -> bool:
    triggers = [
        "help",
        "danger",
        "controlled",
        "trapped",
        "forced",
        "cannot leave",
        "can't leave",
        "being exploited",
        "someone is being exploited",
        "someone is being controlled",
        "i need help",
        "i think this is trafficking",
        "report trafficking",
    ]
    return any(t in text for t in triggers)


def is_yes(text: str) -> bool:
    yes_words = ["yes", "yeah", "y", "immediate danger", "in danger", "urgent"]
    return any(word == text or word in text for word in yes_words)


def is_no(text: str) -> bool:
    no_words = ["no", "nope", "not right now", "not immediate", "safe for now"]
    return any(word == text or word in text for word in no_words)


def get_location_response(text: str):
    if "california" in text:
        return {
            "reply": (
                "If you are in California:\n\n"
                "• Call 911 if there is immediate danger\n"
                "• National Human Trafficking Hotline: 1-888-373-7888\n"
                "• Text: 233733\n"
                "• Website: https://humantraffickinghotline.org\n\n"
                "They are available 24/7 and can help safely."
            ),
            "source": "https://humantraffickinghotline.org",
            "type": "hfj",
            "title": "Support in California",
        }

    if "ireland" in text:
        return {
            "reply": (
                "If you are in Ireland:\n\n"
                "• Call 112 or 999 if there is immediate danger\n"
                "• Use approved local authorities or support services\n\n"
                "If you want, I can help guide you on the safest next step."
            ),
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": "Support in Ireland",
        }

    return None


@app.get("/")
def root():
    return {"message": "HFJ Assistant is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    user_input = req.message.strip()
    text = normalize(user_input)

    if not user_input:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    session_id = req.session_id or str(uuid.uuid4())
    session = SESSION_STATE.setdefault(session_id, {"stage": None})

    # Stage 1: waiting for danger answer
    if session["stage"] == "awaiting_danger":
        if is_yes(text):
            session["stage"] = "awaiting_location"
            return {
                "reply": (
                    "If someone is in immediate danger, contact emergency services right away.\n\n"
                    "Please now tell me the country or state so I can show the most relevant support route."
                ),
                "source": "https://hopeforjustice.org/get-help/",
                "type": "hfj",
                "title": "Emergency support",
                "session_id": session_id,
            }

        if is_no(text):
            session["stage"] = "awaiting_location"
            return {
                "reply": (
                    "Thank you. Please tell me the country or state, for example California or Ireland, "
                    "and I’ll guide you to the right support route."
                ),
                "source": "https://hopeforjustice.org/get-help/",
                "type": "hfj",
                "title": "Location needed",
                "session_id": session_id,
            }

        return {
            "reply": (
                "Please reply yes or no: is anyone in immediate danger right now?"
            ),
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": "Immediate danger check",
            "session_id": session_id,
        }

    # Stage 2: waiting for location
    if session["stage"] == "awaiting_location":
        loc = get_location_response(text)
        if loc:
            loc["session_id"] = session_id
            session["stage"] = None
            return loc

        return {
            "reply": (
                "Please tell me the country or state so I can guide you properly. "
                "For example: California or Ireland."
            ),
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": "Location needed",
            "session_id": session_id,
        }

    # Direct location handling
    loc = get_location_response(text)
    if loc:
        loc["session_id"] = session_id
        return loc

    # Start guided help flow
    if is_help_trigger(text):
        session["stage"] = "awaiting_danger"
        return {
            "reply": (
                "I’m sorry this may be happening.\n\n"
                "Is anyone in immediate danger right now? Please reply yes or no."
            ),
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": "Immediate danger check",
            "session_id": session_id,
        }

    # Mini-RAG
    match = find_match(text)
    if match:
        return {
            "reply": match["answer"],
            "source": match["source"],
            "type": "hfj",
            "title": match["title"],
            "session_id": session_id,
        }

    # OpenAI fallback
    if not client:
        raise HTTPException(status_code=500, detail="Missing API key")

    try:
        response = client.responses.create(
            model="gpt-4o",
            input=f"""
You are the Hope for Justice assistant.

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
            "title": "General guidance",
            "session_id": session_id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
