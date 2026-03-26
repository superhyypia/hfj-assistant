from fastapi import FastAPI
from pydantic import BaseModel
import os
from openai import OpenAI

app = FastAPI()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def root():
    return {"message": "HFJ Assistant is running"}

@app.post("/chat")
def chat(req: ChatRequest):
    user_input = req.message

    # Simple safety routing first
    text = user_input.lower()
    if "help" in text or "danger" in text or "controlled" in text:
        return {
            "reply": (
                "I’m sorry this may be happening. If someone is in immediate danger, "
                "please contact emergency services. Tell me your country or state and I’ll guide you to the right support."
            )
        }

    # Otherwise use AI
    response = client.responses.create(
        model="gpt-5.3",
        input=f"""
You are the Hope for Justice assistant.

Your role:
- Explain human trafficking
- Help users spot the signs
- Be clear, calm, and supportive

Question: {user_input}
"""
    )

    return {
        "reply": response.output_text
    }
