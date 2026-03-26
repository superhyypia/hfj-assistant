from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from openai import OpenAI

app = FastAPI()

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

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
    user_input = req.message
    text = user_input.lower()

    if "help" in text or "danger" in text or "controlled" in text:
        return {
            "reply": (
                "I’m sorry this may be happening. If someone is in immediate danger, "
                "please contact emergency services. Tell me your country or state and I’ll guide you to the right support."
            )
        }

    if not api_key or client is None:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")

    try:
        response = client.responses.create(
            model="gpt-4o",
            input=f"""
You are the Hope for Justice assistant.

Your role:
- Explain human trafficking
- Help users spot the signs
- Be clear, calm, and supportive

Question: {user_input}
"""
        )

        return {"reply": response.output_text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
