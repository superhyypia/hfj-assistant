from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from openai import OpenAI

app = FastAPI()

# Enable CORS for browser UI
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
# MINI RAG KNOWLEDGE BASE
# ------------------------
HFJ_KNOWLEDGE = [
    {
        "id": "what_is_trafficking",
        "title": "What is human trafficking?",
        "source": "https://hopeforjustice.org/human-trafficking/",
        "keywords": [
            "what is human trafficking",
            "what is trafficking",
            "define trafficking",
            "human trafficking meaning",
        ],
        "answer": (
            "Human trafficking is the exploitation of another person for labour, "
            "services, or commercial sex through force, fraud, or coercion. "
            "It is not only about movement — the key issue is exploitation.\n\n"
            "It can affect adults and children and includes labour trafficking, "
            "sexual exploitation, domestic servitude, criminal exploitation, and forced marriage."
        ),
    },
    {
        "id": "spot_the_signs",
        "title": "Spot the signs",
        "source": "https://hopeforjustice.org/spot-the-signs/",
        "keywords": [
            "spot the signs",
            "signs of trafficking",
            "warning signs",
            "how do i spot",
        ],
        "answer": (
            "Some common warning signs may include:\n\n"
            "• Someone appears fearful, anxious, or unable to speak freely\n"
            "• Another person controls their movements or identity documents\n"
            "• They have little freedom of movement or seem dependent\n"
            "• They may be unpaid or underpaid\n"
            "• Poor living conditions or signs of neglect\n\n"
            "Signs can vary depending on the type of exploitation."
        ),
    },
    {
        "id": "get_help",
        "title": "Get help",
        "source": "https://hopeforjustice.org/get-help/",
        "keywords": [
            "get help",
            "i need help",
            "someone is being controlled",
        ],
        "answer": (
            "If someone may be in immediate danger, contact emergency services first.\n\n"
            "Tell me your country or state and I can guide you to the correct support route."
        ),
    },
    {
        "id": "labour_trafficking",
        "title": "Labour trafficking",
        "source": "https://hopeforjustice.org/human-trafficking/",
        "keywords": [
            "labour trafficking",
            "labor trafficking",
            "forced labour",
            "work exploitation",
        ],
        "answer": (
            "Labour trafficking happens when a person is exploited for work through force, fraud, or coercion.\n\n"
            "It may involve low or no pay, threats, long hours, poor conditions, restricted movement, "
            "or someone else controlling identity documents.\n\n"
            "It can occur in agriculture, hospitality, construction, domestic work, and more."
        ),
    },
    {
        "id": "sex_trafficking",
        "title": "Sex trafficking",
        "source": "https://hopeforjustice.org/human-trafficking/",
        "keywords": [
            "sex trafficking",
            "sexual exploitation",
            "forced prostitution",
        ],
        "answer": (
            "Sex trafficking involves exploiting a person for commercial sex through force, fraud, or coercion.\n\n"
            "It may involve control, threats, manipulation, or violence. A person may appear monitored, "
            "unable to speak freely, or controlled by another individual."
        ),
    },
    {
        "id": "reporting_guidance",
        "title": "Reporting guidance",
        "source": "https://hopeforjustice.org/get-help/",
        "keywords": [
            "how do i report",
            "report trafficking",
            "report exploitation",
        ],
        "answer": (
            "If you suspect trafficking, do not confront a suspected trafficker.\n\n"
            "If there is immediate danger, contact emergency services.\n\n"
            "The safest next step is to use official reporting channels. "
            "Tell me your location and I can guide you."
        ),
    },
]


# ------------------------
# HELPERS
# ------------------------
def normalize_text(text: str) -> str:
    return text.lower().strip()


def is_help_query(text: str) -> bool:
    terms = ["help", "danger", "controlled", "trapped", "forced", "can't leave"]
    return any(term in text for term in terms)


def find_knowledge_match(text: str):
    best_match = None
    best_score = 0

    for item in HFJ_KNOWLEDGE:
        score = sum(1 for kw in item["keywords"] if kw in text)
        if score > best_score:
            best_score = score
            best_match = item

    return best_match if best_score > 0 else None


def get_location_response(text: str):
    if "california" in text:
        return {
            "reply": (
                "If you are in California:\n\n"
                "• Emergency: Call 911\n"
                "• Hotline: 1-888-373-7888\n"
                "• Text: 233733\n"
                "• https://humantraffickinghotline.org"
            ),
            "source": "https://humantraffickinghotline.org",
        }

    if "ireland" in text:
        return {
            "reply": (
                "If you are in Ireland:\n\n"
                "• Emergency: 112 or 999\n"
                "• Contact local authorities or approved services"
            ),
            "source": "https://hopeforjustice.org/get-help/",
        }

    return None


# ------------------------
# ROUTES
# ------------------------
@app.get("/")
def root():
    return {"message": "HFJ Assistant is running"}


@app.post("/chat")
def chat(req: ChatRequest):
    user_input = req.message
    text = normalize_text(user_input)

    # 1. Location
    loc = get_location_response(text)
    if loc:
        return loc

    # 2. Help flow
    if is_help_query(text):
        return {
            "reply": (
                "I’m sorry this may be happening. If someone is in immediate danger, "
                "contact emergency services.\n\n"
                "Tell me your country or state and I’ll guide you."
            ),
            "source": "https://hopeforjustice.org/get-help/",
        }

    # 3. Mini-RAG
    match = find_knowledge_match(text)
    if match:
        return {
            "reply": match["answer"],
            "source": match["source"],
            "title": match["title"],
        }

    # 4. AI fallback
    if not client:
        raise HTTPException(status_code=500, detail="Missing OpenAI key")

    response = client.responses.create(
        model="gpt-4o",
        input=f"""
You are the Hope for Justice assistant.

Provide clear, structured, supportive answers about trafficking.

Question: {user_input}
"""
    )

    return {
        "reply": response.output_text,
        "source": "AI-generated",
    }
