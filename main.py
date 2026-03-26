from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from openai import OpenAI

app = FastAPI()

# CORS (for browser UI)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None


class ChatRequest(BaseModel):
    message: str


# ------------------------
# MINI RAG KNOWLEDGE
# ------------------------
HFJ_KNOWLEDGE = [
    {
        "title": "What is human trafficking?",
        "source": "https://hopeforjustice.org/human-trafficking/",
        "keywords": ["what is human trafficking", "define trafficking"],
        "answer": (
            "Human trafficking is the exploitation of another person for labour, "
            "services, or commercial sex through force, fraud, or coercion.\n\n"
            "It is not just about movement — the key issue is exploitation."
        ),
    },
    {
        "title": "Spot the signs",
        "source": "https://hopeforjustice.org/spot-the-signs/",
        "keywords": ["spot the signs", "warning signs", "how do i spot"],
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
        "keywords": ["labour trafficking", "forced labour"],
        "answer": (
            "Labour trafficking involves exploitation through work.\n\n"
            "It may include low pay, threats, long hours, and restricted movement."
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


def normalize(text):
    return text.lower().strip()


def find_match(text):
    for item in HFJ_KNOWLEDGE:
        for kw in item["keywords"]:
            if kw in text:
                return item
    return None


def is_help(text):
    return any(x in text for x in ["help", "danger", "controlled", "trapped"])


def location(text):
    if "california" in text:
        return {
            "reply": (
                "If you are in California:\n\n"
                "• Call 911 in an emergency\n"
                "• Hotline: 1-888-373-7888\n"
                "• Text: 233733\n"
                "• https://humantraffickinghotline.org"
            ),
            "source": "https://humantraffickinghotline.org",
            "type": "hfj"
        }

    if "ireland" in text:
        return {
            "reply": (
                "If you are in Ireland:\n\n"
                "• Emergency: 112 or 999\n"
                "• Contact local services"
            ),
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj"
        }

    return None


@app.get("/")
def root():
    return {"message": "HFJ Assistant is running"}


@app.post("/chat")
def chat(req: ChatRequest):
    text = normalize(req.message)

    # Location
    loc = location(text)
    if loc:
        return loc

    # Help flow
    if is_help(text):
        return {
            "reply": (
                "If someone is in immediate danger, contact emergency services.\n\n"
                "Tell me your location and I can guide you."
            ),
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj"
        }

    # Mini RAG
    match = find_match(text)
    if match:
        return {
            "reply": match["answer"],
            "source": match["source"],
            "type": "hfj"
        }

    # AI fallback
    if not client:
        raise HTTPException(status_code=500, detail="Missing API key")

    response = client.responses.create(
        model="gpt-4o",
        input=f"Explain clearly: {req.message}"
    )

    return {
        "reply": response.output_text,
        "source": "AI-generated",
        "type": "ai"
    }
