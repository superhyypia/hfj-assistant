def polish_retrieved_answer(query: str, retrieved_text: str, language: str = "en") -> str:
    client = get_openai_client()
    if not client:
        return retrieved_text

    response_language = "Spanish" if language == "es" else "English"

    response = client.responses.create(
        model="gpt-4o-mini",
        input=f"""
You are polishing a trusted support answer for a trafficking-awareness assistant.

Respond in {response_language}.

You must ONLY use the information provided in the retrieved text below.
Do NOT add facts, phone numbers, organisations, or advice that are not present in the retrieved text.
Do NOT mention that you are using retrieved text.

Formatting rules:
- Keep the answer concise
- Prefer short bullet points for signs, steps, or key facts
- Use plain language
- No markdown headings
- Maximum 5 bullets
- If the query asks "what is", answer in 1 short paragraph followed by bullets only if helpful
- If the query asks about signs, warning signs, or indicators, use bullets
- If the retrieved text is not sufficient, keep the answer brief and conservative

User question:
{query}

Retrieved text:
{retrieved_text}
"""
    )

    return response.output_text.strip() if response.output_text else retrieved_text
