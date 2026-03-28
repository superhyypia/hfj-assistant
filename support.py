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
        "extra_sources": [
            "https://humantraffickinghotline.org/en/contact",
            "https://humantraffickinghotline.org/en/find-local-services",
        ],
        "type": "hfj",
        "title": title,
    }


def build_country_response(country_name: str, language: str = "en"):
    country_key = normalize_country_key(country_name)
    route = get_support_route(country_key)
    display_name = country_name.strip()

    if route:
        if language == "es":
            reply_lines = [
                f"Si estás en {route['display_name']}:",
                "",
                f"• {route['emergency_text']}",
            ]
            if route["phone"]:
                reply_lines.append(f"• Contacto de apoyo: {route['phone']}")
            if route["website"]:
                reply_lines.append(f"• Sitio web: {route['website']}")
            title = f"Apoyo en {route['display_name']}"
        else:
            reply_lines = [
                f"If you are in {route['display_name']}:",
                "",
                f"• {route['emergency_text']}",
            ]
            if route["phone"]:
                reply_lines.append(f"• Support contact: {route['phone']}")
            if route["website"]:
                reply_lines.append(f"• Website: {route['website']}")
            title = f"Support in {route['display_name']}"

        result = {
            "reply": "\n".join(reply_lines),
            "source": route["website"] or "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": title,
        }

        is_thin_route = (
            not route.get("phone") and
            (
                not route.get("website")
                or route.get("website") == "https://hopeforjustice.org/get-help/"
            )
        )

        if is_thin_route:
            ai_contacts = get_ai_country_support(route["display_name"], language=language)
            if ai_contacts:
                result["additional_contacts_title"] = ai_contacts.get("title")
                result["additional_contacts_status"] = ai_contacts.get("status", "verify")
                result["additional_contacts"] = ai_contacts.get("contacts", [])
                result["additional_contacts_raw_text"] = ai_contacts.get("raw_text", "")

        return result

    if language == "es":
        reply = (
            f"Si estás en {display_name}:\n\n"
            "• Si hay peligro inmediato, contacta de inmediato con los servicios de emergencia locales\n"
            "• Busca ayuda de las autoridades locales oficiales o de organizaciones de apoyo de confianza\n\n"
            "He incluido la información de ayuda de Hope for Justice mientras buscas el apoyo oficial local adecuado."
        )
        title = f"Apoyo en {display_name}"
    else:
        reply = (
            f"If you are in {display_name}:\n\n"
            "• If there is immediate danger, contact local emergency services right away\n"
            "• Seek help from official local authorities or trusted local support organisations\n\n"
            "I’ve included Hope for Justice help information below while you seek the appropriate local official support."
        )
        title = f"Support in {display_name}"

    result = {
        "reply": reply,
        "source": "https://hopeforjustice.org/get-help/",
        "type": "hfj",
        "title": title,
    }

    ai_contacts = get_ai_country_support(display_name, language=language)
    if ai_contacts:
        result["additional_contacts_title"] = ai_contacts.get("title")
        result["additional_contacts_status"] = ai_contacts.get("status", "verify")
        result["additional_contacts"] = ai_contacts.get("contacts", [])
        result["additional_contacts_raw_text"] = ai_contacts.get("raw_text", "")

    return result


def build_help_prompt(location: dict | None, session_id: str, language: str = "en"):
    if location and location.get("confidence") == "high":
        if language == "es":
            reply = (
                "Siento mucho que esto pueda estar ocurriendo.\n\n"
                "Si hay peligro inmediato, contacta ahora con los servicios de emergencia.\n\n"
                f"Entiendo que puedes estar en {location['value']}. Si es así, puedo orientarte hacia opciones de apoyo para ese lugar."
            )
            title = "Apoyo inmediato"
        else:
            reply = (
                "I’m really sorry this may be happening.\n\n"
                "If there is immediate danger, contact emergency services now.\n\n"
                f"I understand you may be in {location['value']}. If that is right, I can guide you to support options for that location."
            )
            title = "Immediate support"

        return {
            "reply": reply,
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": title,
            "session_id": session_id,
        }

    if language == "es":
        reply = (
            "Siento mucho que esto pueda estar ocurriendo.\n\n"
            "Si hay peligro inmediato, contacta ahora con los servicios de emergencia.\n\n"
            "Por favor, dime tu país o estado y te daré las opciones de apoyo adecuadas."
        )
        title = "Apoyo inmediato"
    else:
        reply = (
            "I’m really sorry this may be happening.\n\n"
            "If there is immediate danger, contact emergency services now.\n\n"
            "Please tell me your country or state and I’ll give you the right support options."
        )
        title = "Immediate support"

    return {
        "reply": reply,
        "source": "https://hopeforjustice.org/get-help/",
        "type": "hfj",
        "title": title,
        "session_id": session_id,
    }


def build_unknown_location_response(session_id: str, language: str = "en"):
    if language == "es":
        reply = (
            "Siento mucho que esto pueda estar ocurriendo.\n\n"
            "Si no sabes dónde estás, intenta priorizar tu seguridad inmediata.\n\n"
            "• Si puedes, busca a una persona segura cerca de ti, como personal de una tienda, farmacia, hospital, estación o recepción\n"
            "• Si estás en peligro inmediato, llama o pide a alguien que llame a los servicios de emergencia\n"
            "• Si puedes usar tu teléfono con seguridad, intenta compartir tu ubicación con alguien de confianza\n"
            "• Si no puedes hablar con seguridad, intenta moverte hacia un lugar público o concurrido\n\n"
            "Si puedes, dime cualquier detalle que conozcas — por ejemplo el idioma de los carteles, un nombre de calle, una tienda, o el país aproximado — y te orientaré mejor."
        )
        title = "Apoyo inmediato"
    else:
        reply = (
            "I’m really sorry this may be happening.\n\n"
            "If you do not know where you are, focus on immediate safety first.\n\n"
            "• If you can, look for a safe nearby person such as staff in a shop, pharmacy, hospital, station, or reception desk\n"
            "• If there is immediate danger, call emergency services or ask someone nearby to call for you\n"
            "• If you can use your phone safely, try sharing your location with someone you trust\n"
            "• If you cannot speak safely, try moving toward a public or busy place\n\n"
            "If you can, tell me anything you do know — for example the language on signs, a street name, a shop name, or the approximate country — and I’ll guide you further."
        )
        title = "Immediate support"

    return {
        "reply": reply,
        "source": "https://hopeforjustice.org/get-help/",
        "type": "hfj",
        "title": title,
        "session_id": session_id,
    }
