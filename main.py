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
    user_input = req.message.strip()
    text = user_input.lower()

    # Location-specific support
    if "california" in text:
        return {
            "reply": (
                "If you are in California:\n\n"
                "• Emergency: Call 911 if there is immediate danger\n"
                "• National Human Trafficking Hotline: 1-888-373-7888\n"
                "• Text: 233733\n"
                "• Website: https://humantraffickinghotline.org\n\n"
                "They are available 24/7 and can help safely."
            )
        }

    if "ireland" in text:
        return {
            "reply": (
                "If you are in Ireland:\n\n"
                "• Emergency: Call 112 or 999 if there is immediate danger\n"
                "• Contact local authorities or approved support services\n\n"
                "If you'd like, I can help guide you to the right next step."
            )
        }

    # Safety / support routing
    if (
        "help" in text
        or "danger" in text
        or "controlled" in text
        or "trapped" in text
        or "forced" in text
        or "can't leave" in text
        or "cannot leave" in text
    ):
        return {
            "reply": (
                "I’m sorry this may be happening. If someone is in immediate danger, "
                "please contact emergency services first.\n\n"
                "Please tell me the country or state, for example California or Ireland, "
                "and I’ll guide you to the right support route."
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
- Explain human trafficking clearly and accurately
- Help users understand and spot the signs
- Provide supportive, calm, and practical guidance
- Use a professional, trusted tone aligned with Hope for Justice

Rules:
- Keep answers clear and structured
- Avoid speculation
- If the user may need help, encourage official support routes
- Do not provide investigative or vigilante advice

Question: {user_input}
"""
        )

        return {"reply": response.output_text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
