from ai import get_ai_country_support
from db import get_db_connection
from utils import normalize_country_key, slugify_state


def get_support_route(region_key: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT region_key, display_name, emergency_text, phone, website
                FROM hfj_support_routes
                WHERE region_key = %s
                """,
                (region_key,),
            )
            row = cur.fetchone()

    if not row:
        return None

    return {
        "region_key": row[0],
        "display_name": row[1],
        "emergency_text": row[2],
        "phone": row[3],
        "website": row[4],
    }


def build_us_state_response(state_name: str, language: str = "en"):
    state_slug = slugify_state(state_name)
    state_page = f"https://humantraffickinghotline.org/en/statistics/{state_slug}"

    if language == "es":
        reply = (
            f"Si estás en {state_name}:\n\n"
            "• Si hay peligro inmediato, llama ahora al 911\n"
            "• Línea Nacional contra la Trata de Personas: 1-888-373-7888\n"
            "• Texto: 233733\n"
            "• También hay chat en vivo y notificación en línea\n\n"
            f"La Línea Nacional contra la Trata de Personas también tiene una página dedicada a {state_name}."
        )
        title = f"Apoyo en {state_name}"
    else:
        reply = (
            f"If you are in {state_name}:\n\n"
            "• If there is immediate danger, call 911 now\n"
            "• National Human Trafficking Hotline: 1-888-373-7888\n"
            "• Text: 233733\n"
            "• Live chat and online reporting are also available\n\n"
            f"The National Human Trafficking Hotline also has a dedicated {state_name} page."
        )
        title = f"Support in {state_name}"

    return {
        "reply": reply,
        "source": state_page,
        "type": "hfj",
        "title": title,
    }


def build_country_response(country_name: str, language: str = "en"):
    country_key = normalize_country_key(country_name)
    route = get_support_route(country_key)
    display_name = country_name.strip()

    if route:
        if language == "es":
            reply = (
                f"Si estás en {route['display_name']}:\n\n"
                f"• {route['emergency_text']}\n"
                + (f"• Contacto: {route['phone']}\n" if route["phone"] else "")
                + (f"• Web: {route['website']}" if route["website"] else "")
            )
            title = f"Apoyo en {route['display_name']}"
        else:
            reply = (
                f"If you are in {route['display_name']}:\n\n"
                f"• {route['emergency_text']}\n"
                + (f"• Contact: {route['phone']}\n" if route["phone"] else "")
                + (f"• Website: {route['website']}" if route["website"] else "")
            )
            title = f"Support in {route['display_name']}"

        result = {
            "reply": reply,
            "source": route["website"] or "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": title,
        }

        # Add AI contacts if weak official coverage
        if not route.get("phone"):
            ai_contacts = get_ai_country_support(route["display_name"], language)
            if ai_contacts:
                result["additional_contacts_title"] = ai_contacts.get("title")
                result["additional_contacts_status"] = ai_contacts.get("status")
                result["additional_contacts"] = ai_contacts.get("contacts", [])

        return result

    # Fallback (no official route)
    if language == "es":
        reply = (
            f"Si estás en {display_name}:\n\n"
            "• Contacta servicios de emergencia locales\n"
            "• Busca ayuda de autoridades u organizaciones confiables"
        )
        title = f"Apoyo en {display_name}"
    else:
        reply = (
            f"If you are in {display_name}:\n\n"
            "• Contact local emergency services\n"
            "• Seek help from trusted local organisations"
        )
        title = f"Support in {display_name}"

    result = {
        "reply": reply,
        "source": "https://hopeforjustice.org/get-help/",
        "type": "hfj",
        "title": title,
    }

    ai_contacts = get_ai_country_support(display_name, language)
    if ai_contacts:
        result["additional_contacts_title"] = ai_contacts.get("title")
        result["additional_contacts_status"] = ai_contacts.get("status")
        result["additional_contacts"] = ai_contacts.get("contacts", [])

    return result


def build_help_prompt(location: dict | None, session_id: str, language: str = "en"):
    if language == "es":
        reply = (
            "Siento mucho que esto pueda estar ocurriendo.\n\n"
            "Por favor dime tu país o estado para darte ayuda adecuada."
        )
        title = "Apoyo inmediato"
    else:
        reply = (
            "I’m really sorry this may be happening.\n\n"
            "Please tell me your country or state so I can guide you."
        )
        title = "Immediate support"

    return {
        "reply": reply,
        "source": "https://hopeforjustice.org/get-help/",
        "type": "hfj",
        "title": title,
        "session_id": session_id,
    }
