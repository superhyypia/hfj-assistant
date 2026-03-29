import json
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ai import embed_texts
from db import get_db_connection
from utils import normalize_whitespace

USER_AGENT = "Mozilla/5.0 (compatible; HFJ-Assistant-MVP/1.6)"

JUNK_PATTERNS = [
    "out of date browser",
    "update your browser",
    "we use cookies",
    "privacy policy",
    "cookie settings",
    "accept cookies",
    "terms and conditions",
    "all rights reserved",
    "skip to content",
    "manage consent",
    "close this notice",
    "phone this field is for validation purposes",
    "sign up to our email updates",
]


def is_junk(text: str) -> bool:
    t = text.lower()
    return any(pattern in t for pattern in JUNK_PATTERNS)


def domain_to_source_site(domain: str) -> str:
    if not domain:
        return "unknown"

    cleaned = domain.lower().strip()
    cleaned = cleaned.replace("https://", "").replace("http://", "")
    cleaned = cleaned.replace("www.", "")
    cleaned = cleaned.split("/")[0]
    cleaned = cleaned.replace(".", "_").replace("-", "_")
    return cleaned


def fetch_page_html(url: str) -> str:
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    return response.text


def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    text = normalize_whitespace(text)
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current = ""

    for p in paragraphs:
        if len(current) + len(p) + 1 <= max_chars:
            current = f"{current}\n{p}".strip()
        else:
            if current:
                chunks.append(current)
            if len(p) <= max_chars:
                current = p
            else:
                for i in range(0, len(p), max_chars):
                    part = p[i : i + max_chars].strip()
                    if part:
                        chunks.append(part)
                current = ""

    if current:
        chunks.append(current)

    return chunks


def parse_page(
    html: str,
    url: str,
    source_id: int | None,
    source_name: str | None,
    source_domain: str | None,
    source_site: str,
    region: str,
    content_type: str,
) -> tuple[str, list[dict]]:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "iframe", "svg", "form"]):
        tag.decompose()

    for selector in ["header", "footer", "nav"]:
        for tag in soup.select(selector):
            tag.decompose()

    main_content = soup.find("main")
    article_content = soup.find("article")
    root = article_content or main_content or soup

    page_title = "Content"
    h1 = root.find("h1")
    if h1:
        page_title = normalize_whitespace(h1.get_text(" ", strip=True))
    elif soup.title:
        page_title = normalize_whitespace(soup.title.get_text(" ", strip=True))

    nodes = root.find_all(["h2", "h3", "p", "li"])
    sections = []
    current_heading = page_title
    buffer = []

    def flush_buffer():
        nonlocal buffer
        if not buffer:
            return

        joined = "\n".join(buffer).strip()
        for chunk in chunk_text(joined):
            sections.append(
                {
                    "source_id": source_id,
                    "source_name": source_name,
                    "source_domain": source_domain,
                    "source_url": url,
                    "source_site": source_site,
                    "region": region,
                    "content_type": content_type,
                    "page_title": page_title,
                    "section_heading": current_heading,
                    "content": chunk,
                }
            )
        buffer = []

    for node in nodes:
        text = normalize_whitespace(node.get_text(" ", strip=True))
        if not text or len(text) < 20:
            continue
        if is_junk(text):
            continue

        if node.name in ["h2", "h3"]:
            flush_buffer()
            current_heading = text
        else:
            buffer.append(text)

    flush_buffer()
    return page_title, sections


def upsert_sections(sections: list[dict]) -> int:
    if not sections:
        return 0

    embeddings = embed_texts([section["content"] for section in sections])

    rows = []
    for idx, section in enumerate(sections, start=1):
        embedding_json = json.dumps(embeddings[idx - 1]) if idx - 1 < len(embeddings) else None
        rows.append(
            (
                section["source_id"],
                section["source_name"],
                section["source_domain"],
                section["source_url"],
                section["source_site"],
                section["region"],
                section["content_type"],
                section["page_title"],
                idx,
                section["section_heading"],
                section["content"],
                embedding_json,
            )
        )

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            source_url = sections[0]["source_url"]
            cur.execute("DELETE FROM hfj_content_chunks WHERE source_url = %s", (source_url,))
            cur.executemany(
                """
                INSERT INTO hfj_content_chunks
                (
                    source_id,
                    source_name,
                    source_domain,
                    source_url,
                    source_site,
                    region,
                    content_type,
                    page_title,
                    chunk_index,
                    section_heading,
                    content,
                    embedding_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
        conn.commit()

    return len(rows)


def get_active_ingest_sources() -> list[dict]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, domain, base_url, region, source_type, priority, status
                FROM hfj_sources
                WHERE status = 'active'
                  AND base_url IS NOT NULL
                  AND TRIM(base_url) <> ''
                ORDER BY priority DESC, name ASC
                """
            )
            rows = cur.fetchall()

    sources = []
    for row in rows:
        source_id = row[0]
        name = row[1]
        domain = row[2]
        base_url = row[3]
        region = row[4] or "global"
        source_type = row[5]
        priority = row[6]
        status = row[7]

        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            continue

        sources.append(
            {
                "id": source_id,
                "name": name,
                "domain": domain,
                "url": base_url,
                "source_site": domain_to_source_site(domain),
                "region": region,
                "content_type": "resource",
                "source_type": source_type,
                "priority": priority,
                "status": status,
            }
        )

    return sources


def ingest_source(source: dict) -> dict:
    try:
        html = fetch_page_html(source["url"])
        page_title, sections = parse_page(
            html=html,
            url=source["url"],
            source_id=source.get("id"),
            source_name=source.get("name"),
            source_domain=source.get("domain"),
            source_site=source["source_site"],
            region=source["region"],
            content_type=source.get("content_type", "resource"),
        )
        count = upsert_sections(sections)

        return {
            "id": source.get("id"),
            "name": source.get("name"),
            "domain": source.get("domain"),
            "url": source["url"],
            "source_site": source["source_site"],
            "region": source["region"],
            "content_type": source.get("content_type", "resource"),
            "page_title": page_title,
            "chunks_ingested": count,
            "status": "ok",
        }
    except Exception as e:
        return {
            "id": source.get("id"),
            "name": source.get("name"),
            "domain": source.get("domain"),
            "url": source.get("url"),
            "source_site": source.get("source_site"),
            "status": "error",
            "error": str(e),
        }


def ingest_all_sources():
    sources = get_active_ingest_sources()
    results = []

    for source in sources:
        results.append(ingest_source(source))

    return results


def ingest_source_by_id(source_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, domain, base_url, region, source_type, priority, status
                FROM hfj_sources
                WHERE id = %s
                """,
                (source_id,),
            )
            row = cur.fetchone()

    if not row:
        raise ValueError(f"Source {source_id} not found")

    if not row[3]:
        raise ValueError(f"Source {source_id} has no base_url")

    source = {
        "id": row[0],
        "name": row[1],
        "domain": row[2],
        "url": row[3],
        "source_site": domain_to_source_site(row[2]),
        "region": row[4] or "global",
        "content_type": "resource",
        "source_type": row[5],
        "priority": row[6],
        "status": row[7],
    }

    return ingest_source(source)
