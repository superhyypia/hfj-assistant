from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def root():
    return {"message": "HFJ Assistant is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/chat")
def chat(req: ChatRequest):
    text = req.message.lower()

    if "spot" in text or "sign" in text:
        return {
            "reply": (
                "Hope for Justice highlights signs such as fear or anxiety, "
                "restricted movement, someone else controlling identity documents, "
                "poor living conditions, and signs of low or no pay."
            ),
            "source": "https://hopeforjustice.org/spot-the-signs/"
        }

    if "help" in text or "danger" in text or "controlled" in text:
        return {
            "reply": (
                "If someone may be in immediate danger, contact emergency services first. "
                "Please tell me the country or state so I can show the right support route."
            ),
            "source": "https://hopeforjustice.org/get-help/"
        }

    return {
        "reply": (
            "I can help explain trafficking-related topics, spot-the-signs guidance, "
            "or route someone to support. Try asking 'How do I spot the signs?'"
        ),
        "source": "https://hopeforjustice.org/"
    }
