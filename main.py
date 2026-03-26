from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
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


class ChatRequest(BaseModel):
    message: str


HFJ_KNOWLEDGE = [
    {
        "id": "what_is_trafficking",
        "title": "What is human trafficking?",
        "source": "https://hopeforjustice.org/human-trafficking/",
        "keywords": [
            "what is human trafficking",
            "what is trafficking",
            "define trafficking",
            "definition of trafficking",
            "human trafficking meaning",
        ],
        "answer": (
            "Human trafficking is the exploitation of another person for labour, "
            "services, or commercial sex through force, fraud, or coercion. "
            "It is not only about movement from one place to another — the key issue is exploitation.\n\n"
            "It can affect adults and children and can take different forms, including labour trafficking, "
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
            "how do i spot the signs",
            "how can i tell",
            "warning signs",
            "signs of exploitation",
        ],
        "answer": (
            "Some common warning signs may include:\n\n"
            "• Someone appears fearful, anxious, confused, or unable to speak freely\n"
            "• Another person seems to control their movements, phone, or identity documents\n"
            "• They may have little freedom of movement or seem dependent on others\n"
            "• They could be unpaid, underpaid, or living where they work\n"
            "• They may show signs of poor health, exhaustion, injuries, or neglect\n\n"
            "Hope for Justice also highlights that signs can vary depending on the form of exploitation, "
            "including labour exploitation, sexual exploitation, domestic servitude, criminal exploitation, "
            "and forced marriage."
        ),
    },
    {
        "id": "get_help",
        "title": "Get help",
        "source": "https://hopeforjustice.org/get-help/",
        "keywords": [
            "get help",
            "i need help",
            "how do i report",
            "report trafficking",
            "someone is being exploited",
            "someone is being controlled",
        ],
        "answer": (
            "If someone may be in immediate danger, contact emergency services first.\n\n"
            "If you want support information, tell me the country or state and I can guide you to the right route. "
            "It is safest to use official support and reporting channels rather than confronting a suspected trafficker directly."
        ),
    },
]


def normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def get_location_response(text: str):
    if "california" in text:
        return {
            "reply": (
                "If you are in California:\n\n"
                "• Emergency: Call 911 if there is immediate danger\n"
                "• National Human Trafficking Hotline: 1-888-373-7888\n"
                "• Text: 233733\n"
                "• Website: https://humantraffickinghotline.org\n\n"
                "They are available 24/7 and can help safely."
            ),
            "source": "https://humantraffickinghotline.org",
        }

    if "ireland" in text:
        return {
            "reply": (
                "If you are in Ireland:\n\n"
                "• Emergency: Call 112 or 999 if there is immediate danger\n"
                "• Contact local authorities or approved support services\n\n"
                "If you'd like, I can also help guide you to the right next step."
            ),
            "source": "https://hopeforjustice.org/get-help/",
        }

    return None


def is_help_query(text: str) -> bool:
    help_terms = [
        "help",
        "danger",
        "controlled",
        "trapped",
        "forced",
        "cannot leave",
        "can't leave",
        "being exploited",
        "being controlled",
        "need support",
    ]
    return any(term in text for term in help_terms)


def find_knowledge_match(text: str):
    best_match = None
    best_score = 0

    for item in HFJ_KNOWLEDGE:
        score = 0
        for keyword in item["keywords"]:
            if keyword in text:
                score += len(keyword)

        if score > best_score:
            best_score = score
            best_match = item

    return best_match if best_score > 0 else None


@app.get("/")
def root():
    return {"message": "HFJ Assistant is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    user_input = req.message.strip()
    text = normalize_text(user_input)

    if not user_input:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # 1. Location-specific support
    location_response = get_location_response(text)
    if location_response:
        return location_response

    # 2. Safety / help routing
    if is_help_query(text):
        return {
            "reply": (
                "I’m sorry this may be happening. If someone is in immediate danger, "
                "please contact emergency services first.\n\n"
                "Please tell me the country or state, for example California or Ireland, "
                "and I’ll guide you to the right support route."
            ),
            "source": "https://hopeforjustice.org/get-help/",
        }

    # 3. Mini-RAG: return approved HFJ knowledge when matched
    knowledge_match = find_knowledge_match(text)
    if knowledge_match:
        return {
            "reply": knowledge_match["answer"],
            "source": knowledge_match["source"],
            "title": knowledge_match["title"],
        }

    # 4. Fallback to OpenAI
    if not api_key or client is None:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")

    try:
        response = client.responses.create(
            model="gpt-4o",
            input=f"""
You are the Hope for Justice assistant.

Your role:
- Explain human trafficking clearly and accurately
- Help users understand and spot the signs
- Provide supportive, calm, and practical guidance
- Use a professional, trusted tone aligned with Hope for Justice

Rules:
- Keep answers clear and structured
- Avoid speculation
- If the user may need help, encourage official support routes
- Do not provide investigative or vigilante advice
- Where possible, stay aligned with these themes:
  - trafficking is about exploitation
  - signs may include fear, control, restricted movement, poor conditions, and dependency
  - immediate danger should be directed to emergency services

Question: {user_input}
"""
        )

        return {
            "reply": response.output_text,
            "source": "AI-generated general guidance",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
