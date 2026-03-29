from db import get_db_connection


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


def _source_meta_for_region(region_key: str) -> dict:
    mapping = {
        "ireland": {
            "source_name": "HSE Ireland",
            "source_domain": "hse.ie",
            "source_site": "hse",
        },
        "uk": {
            "source_name": "UK Modern Slavery Helpline",
            "source_domain": "modernslavery.gov.uk",
            "source_site": "modernslavery_uk",
        },
        "united_states": {
            "source_name": "US National Human Trafficking Hotline",
            "source_domain": "humantraffickinghotline.org",
            "source_site": "humantraffickinghotline",
        },
        "canada": {
            "source_name": "Canadian Human Trafficking Hotline",
            "source_domain": "canadianhumantraffickinghotline.ca",
            "source_site": "canadianhumantraffickinghotline",
        },
        "belgium": {
            "source_name": "Hope for Justice",
            "source_domain": "hopeforjustice.org",
            "source_site": "hopeforjustice",
        },
    }
    return mapping.get(
        region_key,
        {
            "source_name": "Hope for Justice",
            "source_domain": "hopeforjustice.org",
            "source_site": "hopeforjustice",
        },
    )


def build_help_prompt(location: dict | None, session_id: str, language: str = "en"):
    if language == "es":
        reply = (
            "Puedo ayudarte a encontrar la opción de apoyo adecuada. "
            "Dime tu país o estado para que pueda orientarte mejor."
        )
        title = "Ubicación necesaria"
    else:
        reply = (
            "I can help find the right support option. "
            "Please tell me your country or state so I can guide you properly."
        )
        title = "Location needed"

    return {
        "reply": reply,
        "source": "https://hopeforjustice.org/get-help/",
        "type": "hfj",
        "title": title,
        "source_site": "hopeforjustice",
        "source_name": "Hope for Justice",
        "source_domain": "hopeforjustice.org",
        "session_id": session_id,
    }


def build_unknown_location_response(session_id: str, language: str = "en"):
    if language == "es":
        reply = (
            "Si no sabes en qué país o estado estás, intenta comunicarte con los servicios "
            "de emergencia locales si existe un peligro inmediato. Si puedes, dime cualquier "
            "detalle de tu ubicación y te ayudaré a encontrar apoyo."
        )
        title = "Apoyo cuando la ubicación no está clara"
    else:
        reply = (
            "If you do not know your country or state, try to contact local emergency services "
            "if there is immediate danger. If you can share any location details, I can help "
            "find the right support options."
        )
        title = "Support when location is unclear"

    return {
        "reply": reply,
        "source": "https://hopeforjustice.org/get-help/",
        "type": "hfj",
        "title": title,
        "source_site": "hopeforjustice",
        "source_name": "Hope for Justice",
        "source_domain": "hopeforjustice.org",
        "session_id": session_id,
    }


def build_low_visibility_response(session_id: str, language: str = "en"):
    if language == "es":
        reply = (
            "Gracias por compartir esto. Si algo no parece correcto, puedo ayudarte a revisar "
            "las señales y encontrar opciones de apoyo. Dime tu país o estado si quieres apoyo local."
        )
        title = "Apoyo y señales"
    else:
        reply = (
            "Thank you for sharing that. If something does not feel right, I can help you review "
            "warning signs and find support options. Tell me your country or state if you want local support."
        )
        title = "Support and warning signs"

    return {
        "reply": reply,
        "source": "https://hopeforjustice.org/spot-the-signs/",
        "type": "hfj",
        "title": title,
        "source_site": "hopeforjustice",
        "source_name": "Hope for Justice",
        "source_domain": "hopeforjustice.org",
        "session_id": session_id,
    }


def build_country_response(country_key: str, language: str = "en"):
    route = get_support_route(country_key)

    if not route:
        if language == "es":
            reply = (
                "No pude encontrar una ruta de apoyo específica para esa ubicación. "
                "Consulta ayuda oficial local o dime otro país o estado."
            )
            title = "Apoyo local no encontrado"
        else:
            reply = (
                "I could not find a specific support route for that location. "
                "Please check official local help or tell me another country or state."
            )
            title = "Local support not found"

        meta = _source_meta_for_region("belgium")
        return {
            "reply": reply,
            "source": "https://hopeforjustice.org/get-help/",
            "type": "hfj",
            "title": title,
            "source_site": meta["source_site"],
            "source_name": meta["source_name"],
            "source_domain": meta["source_domain"],
        }

    if language == "es":
        lines = [f"Si estás en {route['display_name']}:"]

        if route.get("emergency_text"):
            lines.append(f"• {route['emergency_text']}")
        if route.get("phone"):
            lines.append(f"• Contacto de apoyo: {route['phone']}")
        if route.get("website"):
            lines.append(f"• Sitio web: {route['website']}")

        title = f"Apoyo en {route['display_name']}"
    else:
        lines = [f"If you are in {route['display_name']}:"]

        if route.get("emergency_text"):
            lines.append(f"• {route['emergency_text']}")
        if route.get("phone"):
            lines.append(f"• Support contact: {route['phone']}")
        if route.get("website"):
            lines.append(f"• Website: {route['website']}")

        title = f"Support in {route['display_name']}"

    meta = _source_meta_for_region(country_key)

    return {
        "reply": "\n\n".join([lines[0], "\n".join(lines[1:])]) if len(lines) > 1 else lines[0],
        "source": route.get("website") or "https://hopeforjustice.org/get-help/",
        "type": "hfj",
        "title": title,
        "source_site": meta["source_site"],
        "source_name": meta["source_name"],
        "source_domain": meta["source_domain"],
    }


def build_us_state_response(state_name: str, language: str = "en"):
    state_slug = state_name.strip().lower().replace(" ", "-")
    source_url = f"https://humantraffickinghotline.org/en/{state_slug}"

    if language == "es":
        reply = (
            f"Si estás en {state_name}, puedes buscar ayuda y servicios locales a través de la "
            f"National Human Trafficking Hotline.\n\n"
            f"• Si existe un peligro inmediato, llama al 911.\n"
            f"• Línea de apoyo: 1-888-373-7888\n"
            f"• Sitio web: {source_url}"
        )
        title = f"Apoyo en {state_name}"
    else:
        reply = (
            f"If you are in {state_name}, you can look for local help and services through the "
            f"National Human Trafficking Hotline.\n\n"
            f"• Call 911 if there is immediate danger.\n"
            f"• Support contact: 1-888-373-7888\n"
            f"• Website: {source_url}"
        )
        title = f"Support in {state_name}"

    return {
        "reply": reply,
        "source": source_url,
        "type": "hfj",
        "title": title,
        "source_site": "humantraffickinghotline",
        "source_name": "US National Human Trafficking Hotline",
        "source_domain": "humantraffickinghotline.org",
    }
