import requests
from bs4 import BeautifulSoup

from db import get_db_connection
from utils import normalize_whitespace

CONTENT_SOURCES = [
    {
        "url": "https://hopeforjustice.org/human-trafficking/",
        "source_site": "hopeforjustice",
        "region": "global",
        "content_type": "education",
    },
    {
        "url": "https://hopeforjustice.org/spot-the-signs/",
        "source_site": "hopeforjustice",
        "region": "global",
        "content_type": "education",
    },
    {
        "url": "https://hopeforjustice.org/get-help/",
        "source_site": "hopeforjustice",
        "region": "global",
        "content_type": "support",
    },
    {
        "url": "https://hopeforjustice.org/contact/",
        "source_site": "hopeforjustice",
        "region": "global",
        "content_type": "support",
    },
    {
        "url": "https://hopeforjustice.org/resources-and-statistics/",
        "source_site": "hopeforjustice",
        "region": "global",
        "content_type": "resource",
    },
    {
        "url": "https://hopeforjustice.org/resources-and-statistics/spot-the-signs-resources/",
        "source_site": "hopeforjustice",
        "region": "global",
        "content_type": "resource",
    },
    {
        "url": "https://www2.hse.ie/services/human-trafficking/",
        "source_site": "hse",
        "region": "ireland",
        "content_type": "support",
    },
    {
        "url": "https://www2.hse.ie/services/domestic-sexual-gender-based-violence/",
        "source_site": "hse",
        "region": "ireland",
        "content_type": "support",
    },
    {
        "url": "https://www.modernslavery.gov.uk/",
        "source_site": "modernslavery_uk",
        "region": "uk",
        "content_type": "reporting",
    },
    {
        "url": "https://www.modernslavery.gov.uk/prompt-sheet-for-working-offline",
        "source_site": "modernslavery_uk",
        "region": "uk",
        "content_type": "reporting",
    },

    {
    "url": "https://humantraffickinghotline.org/en/contact",
    "source_site": "humantraffickinghotline",
    "region": "united_states",
    "content_type": "support",
},
{
    "url": "https://humantraffickinghotline.org/en/find-local-services",
    "source_site": "humantraffickinghotline",
    "region": "united_states",
    "content_type": "support",
},
{
    "url": "https://humantraffickinghotline.org/en/statistics/california",
    "source_site": "humantraffickinghotline",
    "region": "united_states",
    "content_type": "support",
},
{
    "url": "https://humantraffickinghotline.org/en/statistics/minnesota",
    "source_site": "humantraffickinghotline",
    "region": "united_states",
    "content_type": "support",
},
{
    "url": "https://humantraffickinghotline.org/en/human-trafficking/recognizing-signs",
    "source_site": "humantraffickinghotline",
    "region": "united_states",
    "content_type": "education",
},
]

USER_AGENT = "Mozilla/5.0 (compatible; HFJ-Assistant-MVP/1.3)"

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
                    part = p[i:i + max_chars].strip()
                    if part:
                        chunks.append(part)
                current = ""

    if current:
        chunks.append(current)

    return chunks


def parse_page(html: str, url: str, source_site: str, region: str, content_type: str) -> tuple[str, list[dict]]:
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

    rows = []
    for idx, section in enumerate(sections, start=1):
        rows.append(
            (
                section["source_url"],
                section["source_site"],
                section["region"],
                section["content_type"],
                section["page_title"],
                idx,
                section["section_heading"],
                section["content"],
            )
        )

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            source_url = sections[0]["source_url"]
            cur.execute("DELETE FROM hfj_content_chunks WHERE source_url = %s", (source_url,))
            cur.executemany(
                """
                INSERT INTO hfj_content_chunks
                (source_url, source_site, region, content_type, page_title, chunk_index, section_heading, content)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
        conn.commit()

    return len(rows)


def ingest_all_sources():
    results = []

    for source in CONTENT_SOURCES:
        try:
            html = fetch_page_html(source["url"])
            page_title, sections = parse_page(
                html=html,
                url=source["url"],
                source_site=source["source_site"],
                region=source["region"],
                content_type=source["content_type"],
            )
            count = upsert_sections(sections)
            results.append(
                {
                    "url": source["url"],
                    "source_site": source["source_site"],
                    "region": source["region"],
                    "content_type": source["content_type"],
                    "page_title": page_title,
                    "chunks_ingested": count,
                    "status": "ok",
                }
            )
        except Exception as e:
            results.append(
                {
                    "url": source["url"],
                    "source_site": source["source_site"],
                    "status": "error",
                    "error": str(e),
                }
            )

    return results
