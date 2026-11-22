"""Small helpers shared by source parsers."""

import re

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1
    )
}


def normalise_date(year: str | None, month: str | None = None, day: str | None = None) -> str | None:
    """Return an ISO-style (possibly partial) date string, or None if no year is available."""
    if not year or not re.fullmatch(r"\d{4}", year.strip()):
        return None
    out = year.strip()
    if month:
        m = month.strip().lower()
        num = int(m) if m.isdigit() else _MONTHS.get(m[:3])
        if num and 1 <= num <= 12:
            out += f"-{num:02d}"
            if day and day.strip().isdigit() and 1 <= int(day) <= 31:
                out += f"-{int(day):02d}"
    return out


def date_from_text(text: str | None) -> str | None:
    """Extract a partial ISO date from free text such as '2021 Mar-Apr' or '2023-05-01'."""
    if not text:
        return None
    iso = re.match(r"^(\d{4})-(\d{2})(?:-(\d{2}))?", text.strip())
    if iso:
        return normalise_date(iso.group(1), iso.group(2), iso.group(3))
    m = re.search(r"(\d{4})(?:\s+([A-Za-z]{3}))?", text)
    return normalise_date(m.group(1), m.group(2)) if m else None


def clean_text(text: str | None) -> str | None:
    """Strip simple HTML/JATS tags and collapse whitespace."""
    if not text:
        return None
    text = re.sub(r"<[^>]+>", " ", text)
    text = " ".join(text.split())
    return text or None


def truncate(text: str | None, limit: int = 3000) -> str | None:
    if text is None or len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"
